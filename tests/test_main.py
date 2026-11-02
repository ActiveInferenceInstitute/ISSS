"""Tests for the ``main`` entry point: configuration and stages 1-4 wiring.

The scraper, the HTTP session, the downloader and the converter are stubbed,
so the test runs offline and writes only inside ``tmp_path``.
"""

import json
import os

import main as pipeline


def test_seed_urls_start_from_link_bearing_pages():
    assert pipeline.SEED_URLS[0] == pipeline.BASE_URL
    assert all(url.startswith("https://") for url in pipeline.SEED_URLS)
    assert "https://www.isss.org/annual-meetings/" in pipeline.SEED_URLS
    assert pipeline.MAX_PAGES > 0


def test_main_discovers_downloads_archives_and_converts(tmp_path, monkeypatch):
    urls = [
        "https://web3.isss.org/proceedings/a.pdf",
        "https://web3.isss.org/proceedings/b.docx",
    ]
    converter_calls = []

    class StubScraper:
        def __init__(self, base_url, seed_urls=None, max_pages=None):
            self.base_url = base_url
            self.seed_urls = seed_urls
            self.max_pages = max_pages

        def start_crawling(self, max_depth=11):
            pass

        def get_document_urls(self):
            return list(urls)

    class StubSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    class StubConverter:
        def __init__(self, download_path, converted_path):
            converter_calls.append((download_path, converted_path))

        def convert_files(self):
            return [{"document_name": "a.pdf", "page_count": 1, "characters": 7}]

    async def stub_save_document(self, session, url):
        os.makedirs(self.save_path, exist_ok=True)
        with open(os.path.join(self.save_path, url.rsplit("/", 1)[-1]), "w") as handle:
            handle.write("payload")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "WebScraper", StubScraper)
    monkeypatch.setattr(pipeline.aiohttp, "ClientSession", StubSession)
    monkeypatch.setattr(pipeline.DocumentDownloader, "save_document", stub_save_document)
    monkeypatch.setattr(pipeline, "FileConverter", StubConverter)

    pipeline.main()

    metadata = json.loads((tmp_path / "archived_documents" / "metadata.json").read_text())
    assert [record["document_name"] for record in metadata] == ["a.pdf", "b.docx"]
    assert [record["document_type"] for record in metadata] == ["pdf", "docx"]
    assert sorted(os.listdir(tmp_path / "downloaded_documents")) == ["a.pdf", "b.docx"]
    # Stage 4 runs on the download directory and writes into the configured path.
    assert converter_calls == [(pipeline.DOWNLOAD_PATH, pipeline.CONVERTED_PATH)]
