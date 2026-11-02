"""Tests for ``document_downloader.DocumentDownloader`` — offline stubs only."""

import asyncio
import os

import document_downloader
from document_downloader import DocumentDownloader


class _FakeContent:
    """Yields the payload in fixed-size chunks like ``aiohttp`` does."""

    def __init__(self, payload, chunk_size=1024):
        self._payload = payload
        self._chunk_size = chunk_size

    async def read(self, size=-1):
        if not self._payload:
            return b""
        chunk, self._payload = self._payload[: self._chunk_size], self._payload[self._chunk_size :]
        return chunk


class _FakeResponse:
    def __init__(self, payload, content_type=None):
        self.content = _FakeContent(payload)
        self.headers = {} if content_type is None else {"Content-Type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    """Records requested URLs and returns the configured payload."""

    def __init__(self, payload=b"document-bytes", content_type=None):
        self.payload = payload
        self.content_type = content_type
        self.requested = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def get(self, url):
        self.requested.append(url)
        return _FakeResponse(self.payload, self.content_type)


def test_save_document_writes_the_payload(tmp_path):
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"proceedings")

    name = asyncio.run(
        downloader.save_document(session, "https://web3.isss.org/proceedings/a.pdf")
    )

    assert session.requested == ["https://web3.isss.org/proceedings/a.pdf"]
    assert name == "a.pdf"
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

    name = asyncio.run(downloader.save_document(session, url))

    assert name == "7584.pdf"
    assert (tmp_path / "7584.pdf").read_bytes() == b"%PDF-1.7"


def test_save_document_keeps_a_known_extension_despite_the_content_type(tmp_path):
    """A server that mislabels a PDF must not produce ``a.pdf.bin`` or similar."""
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"payload", content_type="text/html; charset=utf-8")

    name = asyncio.run(
        downloader.save_document(session, "https://web3.isss.org/proceedings/a.pdf")
    )

    assert name == "a.pdf"
    assert sorted(os.listdir(tmp_path)) == ["a.pdf"]


def test_with_content_type_extension_leaves_unknown_types_alone():
    assert DocumentDownloader.with_content_type_extension("7584", None) == "7584"
    assert DocumentDownloader.with_content_type_extension("7584", "text/plain") == "7584"
    assert DocumentDownloader.with_content_type_extension(
        "7584", "APPLICATION/PDF; charset=binary"
    ) == "7584.pdf"
    assert DocumentDownloader.with_content_type_extension(
        "deck.PPTX", "application/pdf"
    ) == "deck.PPTX"


def test_save_document_skips_an_existing_file(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"already-here")
    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    session = _FakeSession(payload=b"replacement")

    name = asyncio.run(
        downloader.save_document(session, "https://web3.isss.org/proceedings/a.pdf")
    )

    assert name == "a.pdf"
    assert session.requested == []
    assert existing.read_bytes() == b"already-here"


def test_download_documents_downloads_every_discovered_url(tmp_path, monkeypatch):
    urls = [
        "https://web3.isss.org/proceedings/a.pdf",
        "https://web3.isss.org/proceedings/b.docx",
    ]
    started = []

    class StubScraper:
        def __init__(self, base_url, seed_urls=None, max_pages=None):
            self.base_url = base_url
            self.seed_urls = seed_urls
            self.max_pages = max_pages

        def start_crawling(self, max_depth=11):
            started.append(max_depth)

        def get_document_urls(self):
            return list(urls)

    monkeypatch.setattr(document_downloader, "WebScraper", StubScraper)
    monkeypatch.setattr(document_downloader.aiohttp, "ClientSession", _FakeSession)

    downloader = DocumentDownloader("https://web3.isss.org", str(tmp_path))
    asyncio.run(downloader.download_documents())

    assert started == [11]
    assert sorted(os.listdir(tmp_path)) == ["a.pdf", "b.docx"]


def test_constructor_forwards_discovery_settings(tmp_path, monkeypatch):
    captured = {}

    class StubScraper:
        def __init__(self, base_url, seed_urls=None, max_pages=None):
            captured["base_url"] = base_url
            captured["seed_urls"] = seed_urls
            captured["max_pages"] = max_pages

    monkeypatch.setattr(document_downloader, "WebScraper", StubScraper)

    DocumentDownloader(
        "https://web3.isss.org",
        str(tmp_path),
        seed_urls=["https://web3.isss.org", "https://www.isss.org/annual-meetings/"],
        max_pages=25,
    )

    assert captured == {
        "base_url": "https://web3.isss.org",
        "seed_urls": ["https://web3.isss.org", "https://www.isss.org/annual-meetings/"],
        "max_pages": 25,
    }
    assert os.path.isdir(tmp_path)
