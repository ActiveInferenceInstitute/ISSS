"""ISSS document processing pipeline entry point.

Discovers documents on the Open ISSS site (https://web3.isss.org), downloads
them, archives their metadata, and converts them into text and page images.
The remaining pipeline stages (figure extraction and language analysis) are
not yet implemented, and the OCR stage stays standalone: it consumes `.jpg`
images, while the conversion stage emits PNG pages and already OCRs the pages
whose PDF text layer is empty. See docs/implementation-status.md for the
current status of each stage.

Run from the repository root:

    python main.py

Configuration lives in the CONFIG block below; see docs/configuration.md.
"""

import asyncio
import os

import aiohttp

from document_downloader import DocumentDownloader
from file_converter import FileConverter
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

# Paths for the stages main.py does not drive: the OCR module demo and the two
# remaining placeholder stages.
OCR_OUTPUT_PATH = 'ocr_texts'
FIGURE_OUTPUT_PATH = 'extracted_figures'
LANGUAGE_ANALYSIS_OUTPUT_PATH = 'language_analysis'


async def _download(urls):
    """Download every discovered document concurrently."""
    downloader = DocumentDownloader(BASE_URL, DOWNLOAD_PATH)
    async with aiohttp.ClientSession() as session:
        tasks = [downloader.save_document(session, url) for url in urls]
        await asyncio.gather(*tasks)


def main():
    # Step 1: discover document URLs on the site
    scraper = WebScraper(BASE_URL, seed_urls=SEED_URLS, max_pages=MAX_PAGES)
    scraper.start_crawling()
    document_urls = scraper.get_document_urls()
    print(f'Discovered {len(document_urls)} document(s).')

    # Step 2: download all documents discovered
    asyncio.run(_download(document_urls))

    # Step 3: archive documents with metadata
    archiver = MetadataArchiver(ARCHIVE_PATH)
    for url in document_urls:
        document_name = url.split('/')[-1]
        document_path = os.path.join(DOWNLOAD_PATH, document_name)
        archiver.archive_metadata(document_path, url, document_name.split('.')[-1])

    # Step 4: convert the downloaded documents into text and page images
    converter = FileConverter(DOWNLOAD_PATH, CONVERTED_PATH)
    converted = converter.convert_files()
    print(f'Converted {len(converted)} document(s) into {CONVERTED_PATH}.')

    # Steps 6-7 (figure extraction, language analysis) are not yet implemented;
    # see docs/implementation-status.md. Stage 5 (OCR) remains standalone.
    print('Pipeline stages 6-7 (figures, language analysis) are not yet implemented.')


if __name__ == '__main__':
    main()
