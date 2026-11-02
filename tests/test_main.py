"""Tests for the ``main`` entry point: configuration and stages 1-7.

The scraper, the HTTP session, the downloader, the converter, the figure
extractor and the analyzer are stubbed, so the test runs offline and writes
only inside ``tmp_path``.
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
        # A journal platform URL whose last segment carries no extension: the
        # downloader names it from the response content type.
        "https://journals.isss.org/index.php/proceedings56th/article/download/1766/611/7584",
    ]
    converter_calls = []
    analyzer_calls = []
    extractor_calls = []

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

    class StubAnalyzer:
        def __init__(self, text_path, output_path):
            analyzer_calls.append((text_path, output_path))

        def analyze_language(self):
            return {"document_count": 0, "documents": [], "totals": {}}

    class StubExtractor:
        def __init__(self, converted_path, figure_output_path):
            extractor_calls.append((converted_path, figure_output_path))

        def extract_figures(self):
            return {"document_count": 0, "figure_count": 0, "documents": []}

    async def stub_save_document(self, session, url):
        name = pipeline.DocumentDownloader.with_content_type_extension(
            pipeline.DocumentDownloader.document_filename(url), "application/pdf"
        )
        os.makedirs(self.save_path, exist_ok=True)
        with open(os.path.join(self.save_path, name), "w") as handle:
            handle.write("payload")
        return name

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "WebScraper", StubScraper)
    monkeypatch.setattr(pipeline.aiohttp, "ClientSession", StubSession)
    monkeypatch.setattr(pipeline.DocumentDownloader, "save_document", stub_save_document)
    monkeypatch.setattr(pipeline, "FileConverter", StubConverter)
    monkeypatch.setattr(pipeline, "LanguageAnalyzer", StubAnalyzer)
    monkeypatch.setattr(pipeline, "FigureExtractor", StubExtractor)

    pipeline.main()

    metadata = json.loads((tmp_path / "archived_documents" / "metadata.json").read_text())
    # The archive step records the names the downloader reported, so a URL
    # without an extension is archived under the name it was downloaded as.
    assert [record["document_name"] for record in metadata] == ["a.pdf", "b.docx", "7584.pdf"]
    assert [record["document_type"] for record in metadata] == ["pdf", "docx", "pdf"]
    assert sorted(os.listdir(tmp_path / "downloaded_documents")) == [
        "7584.pdf",
        "a.pdf",
        "b.docx",
    ]
    # Stage 4 runs on the download directory and writes into the configured path.
    assert converter_calls == [(pipeline.DOWNLOAD_PATH, pipeline.CONVERTED_PATH)]
    # Stage 6 reads the converted pages and writes its own artifact path.
    assert extractor_calls == [(pipeline.CONVERTED_PATH, pipeline.FIGURE_OUTPUT_PATH)]
    # Stage 7 analyses the text stage 4 wrote and writes its own artifact path.
    assert analyzer_calls == [
        (os.path.join(pipeline.CONVERTED_PATH, "text"), pipeline.LANGUAGE_ANALYSIS_OUTPUT_PATH)
    ]
