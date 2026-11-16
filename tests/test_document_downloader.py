"""Tests for ``document_downloader.DocumentDownloader`` — offline stubs only."""

import asyncio
import json

import pytest

import document_downloader
from document_downloader import DocumentDownloader, DownloadError
from web_scraper import CrawlResult


class _FakeContent:
    """Yields the payload in fixed-size chunks like ``aiohttp`` does."""

    def __init__(self, payload, chunk_size=1024, fail_after=None):
        self._payload = payload
        self._chunk_size = chunk_size
        self._reads = 0
        self._fail_after = fail_after

    async def read(self, size=-1):
        await asyncio.sleep(0)
        if self._fail_after is not None and self._reads >= self._fail_after:
            raise OSError('interrupted stream')
        self._reads += 1
        if not self._payload:
            return b""
        chunk, self._payload = self._payload[: self._chunk_size], self._payload[self._chunk_size :]
        return chunk


class _FakeResponse:
    def __init__(self, payload=b'document', content_type=None, status=200, headers=None,
                 fail_after=None):
        self.content = _FakeContent(payload, fail_after=fail_after)
        self.status = status
        self.headers = dict(headers or {})
        if content_type is not None:
            self.headers['Content-Type'] = content_type

    def raise_for_status(self):
        if self.status >= 400:
            raise OSError(f'HTTP {self.status}')

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    """Records requested URLs and returns the configured payload."""

    def __init__(self, payload=b"document-bytes", content_type=None, routes=None, **options):
        self.payload = payload
        self.content_type = content_type
        self.routes = routes or {}
        self.options = options
        self.requested = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        self.requested.append(url)
        options = dict(self.routes.get(url, {
            'payload': self.payload, 'content_type': self.content_type, **self.options
        }))
        return _FakeResponse(**options)


def test_save_document_writes_the_payload(tmp_path):
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"proceedings")

    receipt = asyncio.run(
        downloader.save_document(session, "https://web3.isss.org/proceedings/a.pdf")
    )

    assert session.requested == ["https://web3.isss.org/proceedings/a.pdf"]
    assert receipt.document_name == "a.pdf"
    assert receipt.validate() == receipt
    assert not receipt.cached
    assert (tmp_path / "a.pdf").read_bytes() == b"proceedings"


def test_document_filename_keeps_the_last_path_segment(tmp_path):
    url = "https://web3.isss.org/proceedings/a%20b.pdf?download=1#page=2"

    assert DocumentDownloader.document_filename(url) == "a b.pdf"


def test_document_filename_falls_back_for_a_directory_url():
    assert DocumentDownloader.document_filename("https://web3.isss.org/proceedings/") == "document"


def test_save_document_names_an_extension_less_url_from_the_content_type(tmp_path):
    """A journal galley URL ends in an id; the response says what the file is."""
    url = "https://journals.isss.org/index.php/proceedings56th/article/download/1766/611/7584"
    downloader = DocumentDownloader("https://journals.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"%PDF-1.7", content_type="application/pdf")

    receipt = asyncio.run(downloader.save_document(session, url))

    assert receipt.document_name == "7584.pdf"
    assert receipt.validate() == receipt
    assert (tmp_path / "7584.pdf").read_bytes() == b"%PDF-1.7"


def test_save_document_keeps_a_known_extension_despite_the_content_type(tmp_path):
    """A server that mislabels a PDF must not produce ``a.pdf.bin`` or similar."""
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"payload", content_type="text/html; charset=utf-8")

    receipt = asyncio.run(
        downloader.save_document(session, "https://web3.isss.org/proceedings/a.pdf")
    )

    assert receipt.document_name == "a.pdf"
    assert (tmp_path / "a.pdf").read_bytes() == b"payload"


def test_with_content_type_extension_leaves_unknown_types_alone():
    assert DocumentDownloader.with_content_type_extension("7584", None) == "7584"
    assert DocumentDownloader.with_content_type_extension("7584", "text/plain") == "7584"
    assert DocumentDownloader.with_content_type_extension(
        "7584", "APPLICATION/PDF; charset=binary"
    ) == "7584.pdf"
    assert DocumentDownloader.with_content_type_extension(
        "deck.PPTX", "application/pdf"
    ) == "deck.PPTX"


def test_save_document_refuses_unreceipted_existing_bytes(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"already-here")
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    with pytest.raises(DownloadError, match="ambiguous"):
        asyncio.run(downloader.save_document(
            _FakeSession(payload=b"replacement"), "https://web3.isss.org/proceedings/a.pdf"
        ))
    assert existing.read_bytes() == b"already-here"
    assert not (tmp_path / '.receipts').exists()


def test_download_documents_returns_receipts_for_each_discovered_url(tmp_path, monkeypatch):
    urls = ("https://web3.isss.org/a.pdf", "https://web3.isss.org/b.docx")
    discovery = CrawlResult('successful', urls, 1, (), False)
    monkeypatch.setattr(
        document_downloader.WebScraper, 'start_crawling', lambda self: discovery
    )
    monkeypatch.setattr(document_downloader.aiohttp, "ClientSession", _FakeSession)
    result = asyncio.run(DocumentDownloader("https://web3.isss.org", tmp_path).download_documents())
    assert result['discovery'] == discovery
    assert result['failures'] == []
    assert [receipt.document_name for receipt in result['receipts']] == ['a.pdf', 'b.docx']
    assert all(receipt.validate() == receipt for receipt in result['receipts'])


@pytest.mark.parametrize('status', [404, 500])
def test_http_failure_never_publishes_document_or_receipt(tmp_path, status):
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    with pytest.raises(DownloadError, match=f'HTTP {status}'):
        asyncio.run(downloader.save_document(
            _FakeSession(status=status), 'https://web3.isss.org/error.pdf'
        ))
    assert not (tmp_path / 'error.pdf').exists()
    assert not (tmp_path / '.receipts').exists()
    assert not list(tmp_path.glob('.download-*'))


def test_interrupted_stream_preserves_history_and_never_becomes_cached(tmp_path):
    history = tmp_path / 'history.pdf'
    history.write_bytes(b'historical bytes')
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    with pytest.raises(DownloadError, match='interrupted'):
        asyncio.run(downloader.save_document(
            _FakeSession(payload=b'partial', fail_after=1), 'https://web3.isss.org/new.pdf'
        ))
    assert history.read_bytes() == b'historical bytes'
    assert not (tmp_path / 'new.pdf').exists()
    assert not list(tmp_path.glob('.download-*'))
    receipt = asyncio.run(downloader.save_document(
        _FakeSession(payload=b'complete'), 'https://web3.isss.org/new.pdf'
    ))
    assert receipt.validate() == receipt
    assert (tmp_path / 'new.pdf').read_bytes() == b'complete'


def test_cache_requires_content_and_preserves_original_acquisition_time(tmp_path):
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    url = 'https://web3.isss.org/a.pdf'
    first = asyncio.run(downloader.save_document(_FakeSession(), url))
    session = _FakeSession(payload=b'must not replace')
    cached = asyncio.run(downloader.save_document(session, url))
    assert cached.cached
    assert cached.download_date == first.download_date
    assert cached.sha256 == first.sha256
    assert session.requested == []
    (tmp_path / 'a.pdf').write_bytes(b'corrupted')
    with pytest.raises(DownloadError, match='content'):
        asyncio.run(downloader.save_document(session, url))
    assert (tmp_path / 'a.pdf').read_bytes() == b'corrupted'


def test_concurrent_competing_urls_never_relabel_shared_basename(tmp_path):
    urls = ('https://web3.isss.org/one/a.pdf', 'https://web3.isss.org/two/a.pdf')
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    session = _FakeSession(routes={
        urls[0]: {'payload': b'first source'}, urls[1]: {'payload': b'second source'}
    })
    receipts, failures = asyncio.run(downloader.download_urls(session, iter(urls)))
    assert len(receipts) == len(failures) == 1
    winner = receipts[0]
    assert winner.validate() == winner
    assert (tmp_path / 'a.pdf').read_bytes() == session.routes[winner.source_url]['payload']
    assert failures[0]['source_url'] != winner.source_url


def test_same_url_concurrently_reuses_one_completed_acquisition(tmp_path):
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    url = 'https://web3.isss.org/a.pdf'
    session = _FakeSession()
    receipts, failures = asyncio.run(downloader.download_urls(session, [url, url]))
    assert failures == []
    assert [receipt.cached for receipt in receipts] == [False, True]
    assert receipts[0].download_date == receipts[1].download_date
    assert session.requested == [url]


def test_off_boundary_redirect_is_not_requested(tmp_path):
    url = 'https://web3.isss.org/a.pdf'
    session = _FakeSession(routes={
        url: {'status': 302, 'headers': {'Location': 'https://notisss.org/a.pdf'}}
    })
    with pytest.raises(DownloadError, match='redirect'):
        asyncio.run(DocumentDownloader("https://web3.isss.org", tmp_path).save_document(session, url))
    assert session.requested == [url]
    assert not (tmp_path / 'a.pdf').exists()


def test_malformed_receipt_is_not_treated_as_a_cache_miss(tmp_path):
    downloader = DocumentDownloader("https://web3.isss.org", tmp_path)
    url = 'https://web3.isss.org/a.pdf'
    asyncio.run(downloader.save_document(_FakeSession(), url))
    path = next((tmp_path / '.receipts').glob('*.json'))
    data = json.loads(path.read_text())
    data['source_url'] = 'https://web3.isss.org/someone-else.pdf'
    path.write_text(json.dumps(data))
    with pytest.raises(DownloadError, match='mismatch'):
        asyncio.run(downloader.save_document(_FakeSession(), url))
    assert (tmp_path / 'a.pdf').read_bytes() == b'document-bytes'


def test_cancelled_acquisition_is_not_returned_as_a_success_receipt(tmp_path, monkeypatch):
    downloader = DocumentDownloader('https://isss.org', tmp_path)

    async def cancelled(session, url):
        raise asyncio.CancelledError()

    monkeypatch.setattr(downloader, 'save_document', cancelled)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(downloader.download_urls(_FakeSession(), ['https://isss.org/a.pdf']))
    assert not (tmp_path / 'a.pdf').exists()


def test_receipt_publication_failure_preserves_bytes_without_claiming_a_cache_hit(
    tmp_path, monkeypatch
):
    downloader = DocumentDownloader('https://isss.org', tmp_path)

    def refuse_receipt(path, value):
        raise OSError('receipt publication failed')

    monkeypatch.setattr(document_downloader, 'atomic_json', refuse_receipt)
    with pytest.raises(DownloadError, match='receipt publication failed'):
        asyncio.run(downloader.save_document(
            _FakeSession(payload=b'complete but unqualified'), 'https://isss.org/one/a.pdf'
        ))
    assert (tmp_path / 'a.pdf').read_bytes() == b'complete but unqualified'
    assert not (tmp_path / '.receipts').exists()
    with pytest.raises(DownloadError, match='ambiguous'):
        asyncio.run(downloader.save_document(
            _FakeSession(payload=b'must not overwrite'), 'https://isss.org/two/a.pdf'
        ))
    assert (tmp_path / 'a.pdf').read_bytes() == b'complete but unqualified'
