"""ISSS document processing pipeline entry point.

Discovers documents on the Open ISSS site (https://web3.isss.org), downloads
them, archives their metadata, converts them into text and page images,
extracts figures with caption candidates from the page images, and compiles
descriptive statistics over the converted text. All seven stages are
implemented; the OCR stage additionally stays standalone, because it consumes
`.jpg` images while the conversion stage emits PNG pages and already OCRs the
pages whose PDF text layer is empty. See docs/implementation-status.md for the
current status of each stage.

Run from the repository root:

    python main.py

Configuration lives in the CONFIG block below; see docs/configuration.md.
"""

import asyncio

import aiohttp

from document_downloader import DocumentDownloader
from figure_extractor import FigureExtractor
from file_converter import FileConverter
from language_analyzer import LanguageAnalyzer
from metadata_archiver import MetadataArchiver
from web_scraper import WebScraper

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = 'https://web3.isss.org'  # Base URL of the Open ISSS site.
# Pages the discovery crawl starts from. The web3 front end alone links no
# documents; the society site links the document paths, including the legacy
# web3.isss.org proceedings. See docs/implementation-status.md.
SEED_URLS = [
    BASE_URL,
    'https://www.isss.org/',
    'https://www.isss.org/annual-meetings/',
]
MAX_PAGES = 250  # Upper bound on pages fetched in one discovery run.
DOWNLOAD_PATH = 'downloaded_documents'  # Where downloaded files are saved.
ARCHIVE_PATH = 'archived_documents'  # Where metadata.json is written.
CONVERTED_PATH = 'converted_documents'  # Where converted text and page images are written.
FIGURE_OUTPUT_PATH = 'extracted_figures'  # Where the extracted figures are written.
LANGUAGE_ANALYSIS_OUTPUT_PATH = 'language_analysis'  # Where the text statistics are written.
# Used by the standalone OCR demo, not by main(): the converted pages are PNG
# and their image-only PDF pages are already OCR'd by stage 4.
OCR_OUTPUT_PATH = 'ocr_texts'


async def _download(urls):
    """Return qualified receipts and explicit per-URL failures, preserving peers."""
    downloader = DocumentDownloader(BASE_URL, DOWNLOAD_PATH)
    async with aiohttp.ClientSession() as session:
        return await downloader.download_urls(session, urls)


def main():
    scraper = WebScraper(BASE_URL, seed_urls=SEED_URLS, max_pages=MAX_PAGES)
    discovery = scraper.start_crawling()
    print(f'Discovery {discovery.status}: {len(discovery.document_urls)} document(s).')
    for failure in discovery.failures:
        print(f'Discovery failure: {failure["url"]}: {failure["error"]}')
    if discovery.status == 'failed':
        print('Pipeline failed during discovery; existing outputs preserved.')
        return 1

    receipts, download_failures = asyncio.run(_download(discovery.document_urls))
    for failure in download_failures:
        print(f'Download failed: {failure["source_url"]}: {failure["error"]}')
    MetadataArchiver(ARCHIVE_PATH).archive_receipts(receipts)

    converter = FileConverter(DOWNLOAD_PATH, CONVERTED_PATH)
    converted = converter.convert_files(
        (receipt.document_path for receipt in receipts),
        expected_identities={
            receipt.document_name: {'sha256': receipt.sha256, 'size': receipt.size}
            for receipt in receipts
        },
    )
    print(f'Converted {len(converted)} document(s) into {CONVERTED_PATH}.')
    figures = FigureExtractor(CONVERTED_PATH, FIGURE_OUTPUT_PATH).extract_figures()
    language = LanguageAnalyzer(CONVERTED_PATH, LANGUAGE_ANALYSIS_OUTPUT_PATH).analyze_language()

    incomplete = bool(
        discovery.status == 'partial' or download_failures or converter.store.failures
        or figures['failures'] or language['failures']
    )
    status = 'partial' if incomplete else discovery.status
    print(f'Pipeline {status}: results in {CONVERTED_PATH}, {FIGURE_OUTPUT_PATH} and '
          f'{LANGUAGE_ANALYSIS_OUTPUT_PATH}.')
    return 1 if incomplete else 0


if __name__ == '__main__':
    raise SystemExit(main())
