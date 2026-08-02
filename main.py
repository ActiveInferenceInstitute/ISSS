"""ISSS document processing pipeline entry point.

Discovers documents on the Open ISSS site (https://web3.isss.org), downloads
them, and archives their metadata. The remaining pipeline stages (file
conversion, OCR, figure extraction, language analysis) are not yet
implemented; see docs/implementation-status.md for the current status of each
stage.

Run from the repository root:

    python main.py

Configuration lives in the CONFIG block below; see docs/configuration.md.
"""

import asyncio
import os

import aiohttp
from document_downloader import DocumentDownloader
from metadata_archiver import MetadataArchiver
from web_scraper import WebScraper

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = 'https://web3.isss.org'  # Site to crawl for documents.
DOWNLOAD_PATH = 'downloaded_documents'  # Where downloaded files are saved.
ARCHIVE_PATH = 'archived_documents'  # Where metadata.json is written.

# Paths reserved for the pipeline stages that are not yet implemented.
CONVERTED_PATH = 'converted_documents'
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
    scraper = WebScraper(BASE_URL)
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

    # Steps 4-7 (file conversion, OCR, figure extraction, language analysis)
    # are not yet implemented; see docs/implementation-status.md.
    print('Pipeline stages 4-7 (conversion, OCR, figures, language analysis) are not yet implemented.')


if __name__ == '__main__':
    main()
