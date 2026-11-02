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
import os

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
    """Download every discovered document concurrently.

    Returns the file names the documents were saved under, in URL order, so the
    archive step records the files that were actually written rather than a name
    derived again from the URL.
    """
    downloader = DocumentDownloader(BASE_URL, DOWNLOAD_PATH)
    async with aiohttp.ClientSession() as session:
        tasks = [downloader.save_document(session, url) for url in urls]
        return await asyncio.gather(*tasks)


def main():
    # Step 1: discover document URLs on the site
    scraper = WebScraper(BASE_URL, seed_urls=SEED_URLS, max_pages=MAX_PAGES)
    scraper.start_crawling()
    document_urls = scraper.get_document_urls()
    print(f'Discovered {len(document_urls)} document(s).')

    # Step 2: download all documents discovered
    document_names = asyncio.run(_download(document_urls))

    # Step 3: archive documents with metadata
    archiver = MetadataArchiver(ARCHIVE_PATH)
    for url, document_name in zip(document_urls, document_names):
        document_path = os.path.join(DOWNLOAD_PATH, document_name)
        archiver.archive_metadata(document_path, url, document_name.split('.')[-1])

    # Step 4: convert the downloaded documents into text and page images
    converter = FileConverter(DOWNLOAD_PATH, CONVERTED_PATH)
    converted = converter.convert_files()
    print(f'Converted {len(converted)} document(s) into {CONVERTED_PATH}.')

    # Step 6: extract the figures and their caption candidates from the pages
    extractor = FigureExtractor(CONVERTED_PATH, FIGURE_OUTPUT_PATH)
    extractor.extract_figures()

    # Step 7: compile descriptive statistics over the converted text
    analyzer = LanguageAnalyzer(os.path.join(CONVERTED_PATH, 'text'), LANGUAGE_ANALYSIS_OUTPUT_PATH)
    analyzer.analyze_language()

    print(f'Pipeline finished: results in {CONVERTED_PATH}, {FIGURE_OUTPUT_PATH} and '
          f'{LANGUAGE_ANALYSIS_OUTPUT_PATH}.')


if __name__ == '__main__':
    main()
