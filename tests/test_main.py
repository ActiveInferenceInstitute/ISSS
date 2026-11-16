"""Consumer-level pipeline regressions; only discovery/HTTP boundaries are replaced."""

import io
import json

import pytest
from docx import Document

import main as pipeline
from pipeline_artifacts import ArtifactStore
from web_scraper import CrawlResult


def _docx_bytes(text):
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize('partial', [False, True])
def test_pipeline_consumes_only_qualified_receipts_and_current_generations(
    tmp_path, monkeypatch, receipt_factory, capsys, partial
):
    monkeypatch.chdir(tmp_path)
    receipt = receipt_factory('good.docx', _docx_bytes('ISSS AI.'))
    legacy = tmp_path / 'downloaded_documents' / 'legacy.docx'
    legacy.write_bytes(_docx_bytes('This unqualified source must never be included.'))
    legacy_bytes = legacy.read_bytes()
    stale_text = tmp_path / 'converted_documents' / 'text' / 'obsolete.txt'
    stale_text.parent.mkdir(parents=True)
    stale_text.write_text('Obsolete output must never enter the corpus.')
    old_figure = tmp_path / 'extracted_figures' / 'unknown.png'
    old_figure.parent.mkdir()
    old_figure.write_bytes(b'unowned crop')
    discovery = CrawlResult(
        'partial' if partial else 'successful', (receipt.source_url,), 1,
        ({'url': 'https://www.isss.org/broken', 'error': 'offline failure'},) if partial else (),
        False,
    )
    monkeypatch.setattr(pipeline.WebScraper, 'start_crawling', lambda self: discovery)

    async def download(urls):
        failures = [{'source_url': 'https://web3.isss.org/missing.pdf', 'error': 'HTTP 500'}]
        return [receipt], failures if partial else []

    monkeypatch.setattr(pipeline, '_download', download)
    assert pipeline.main() == (1 if partial else 0)
    archive = tmp_path / 'archived_documents' / 'metadata.json'
    rows = json.loads(archive.read_text())
    assert [row['document_name'] for row in rows] == ['good.docx']
    assert rows[0]['download_date'] == '2020-01-02T03:04:05+00:00'
    report = json.loads((tmp_path / 'language_analysis' / 'language_analysis.json').read_text())
    assert report['document_count'] == 1
    assert report['totals']['words'] == 2
    assert report['totals']['average_words_per_sentence'] == 2.0
    store = ArtifactStore(tmp_path / 'converted_documents', 'conversion')
    active = store.active_documents()
    assert [entry['document_name'] for entry in active] == ['good.docx']
    original_text = store.resolve(active[0], active[0]['text_file'])
    original_bytes = original_text.read_bytes()
    assert legacy.read_bytes() == legacy_bytes
    assert stale_text.read_text() == 'Obsolete output must never enter the corpus.'
    assert old_figure.read_bytes() == b'unowned crop'
    assert pipeline.main() == (1 if partial else 0)
    assert json.loads(archive.read_text()) == rows
    assert original_text.read_bytes() == original_bytes
    assert ('Pipeline partial:' if partial else 'Pipeline successful:') in capsys.readouterr().out


def test_failed_discovery_preserves_outputs_and_is_not_empty_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / 'converted_documents' / 'active.json'
    marker.parent.mkdir()
    marker.write_bytes(b'previous complete evidence')
    failed = CrawlResult('failed', (), 0, ({'url': 'bad', 'error': 'refused'},), False)
    monkeypatch.setattr(pipeline.WebScraper, 'start_crawling', lambda self: failed)

    async def forbidden_download(urls):
        raise AssertionError('failed discovery must not start acquisition')

    monkeypatch.setattr(pipeline, '_download', forbidden_download)
    assert pipeline.main() == 1
    assert marker.read_bytes() == b'previous complete evidence'
    assert 'Pipeline failed during discovery' in capsys.readouterr().out


def test_successful_empty_discovery_publishes_empty_current_sets(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    empty = CrawlResult('successful-empty', (), 1, (), False)
    monkeypatch.setattr(pipeline.WebScraper, 'start_crawling', lambda self: empty)

    async def no_documents(urls):
        return [], []

    monkeypatch.setattr(pipeline, '_download', no_documents)
    assert pipeline.main() == 0
    current = json.loads((tmp_path / 'converted_documents' / 'active.json').read_text())
    assert current['documents'] == []
    assert current['failures'] == {}
    assert 'Pipeline successful-empty:' in capsys.readouterr().out


def test_download_batch_returns_successful_peers_and_explicit_failures(
    tmp_path, monkeypatch, receipt_factory
):
    monkeypatch.chdir(tmp_path)
    receipt = receipt_factory('good.docx', _docx_bytes('Qualified document.'))

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def acquire(self, session, url):
        if url == receipt.source_url:
            return receipt
        raise RuntimeError('HTTP 500 fixture')

    monkeypatch.setattr(pipeline.aiohttp, 'ClientSession', Session)
    monkeypatch.setattr(pipeline.DocumentDownloader, 'save_document', acquire)
    receipts, failures = pipeline.asyncio.run(pipeline._download([
        receipt.source_url, 'https://isss.org/missing.pdf'
    ]))
    assert receipts == [receipt]
    assert failures == [{
        'source_url': 'https://isss.org/missing.pdf', 'error': 'HTTP 500 fixture'
    }]
    assert receipt.validate() == receipt
