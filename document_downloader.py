import asyncio
import os
from urllib.parse import unquote, urlsplit

import aiohttp

from web_scraper import WebScraper  # Import the WebScraper class

#: Document extensions the later stages convert.
DOCUMENT_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx')
#: Extension to use when the URL path carries none but the content type does.
CONTENT_TYPE_EXTENSIONS = {
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
}


class DocumentDownloader:
    def __init__(self, base_url, save_path, seed_urls=None, max_pages=None):
        self.base_url = base_url
        self.save_path = save_path
        # Ensure the save path exists
        os.makedirs(save_path, exist_ok=True)
        # Initialize the WebScraper
        self.scraper = WebScraper(base_url, seed_urls=seed_urls, max_pages=max_pages)

    @staticmethod
    def document_filename(url):
        """Returns the file name a document URL is saved under.

        The name is the last segment of the URL path, so a query string or a
        fragment cannot leak into the file name.

        Args:
            url (str): The document URL.

        Returns:
            str: The file name, without a directory part.
        """
        return os.path.basename(unquote(urlsplit(url).path)) or 'document'

    @staticmethod
    def with_content_type_extension(filename, content_type):
        """Adds the extension a response content type implies, when missing.

        Journal platforms hand out document URLs whose last path segment carries
        no extension (for example
        ``https://journals.isss.org/index.php/proceedings56th/article/download/1766/611/7584``).
        Without this step such a document would be saved as ``7584`` and then
        skipped by the conversion stage, which selects on the extension.

        Args:
            filename (str): The file name derived from the URL.
            content_type (str | None): The response's ``Content-Type`` header.

        Returns:
            str: The file name, extended when it had no document extension and
            the content type is one the pipeline converts; otherwise unchanged.
        """
        if filename.lower().endswith(DOCUMENT_EXTENSIONS):
            return filename
        media_type = (content_type or '').split(';')[0].strip().lower()
        extension = CONTENT_TYPE_EXTENSIONS.get(media_type)
        return f'{filename}{extension}' if extension else filename

    async def save_document(self, session, url):
        """Downloads one document unless a file of that name already exists.

        Args:
            session (aiohttp.ClientSession): The session to download with.
            url (str): The document URL.

        Returns:
            str: The file name the document was saved under, so a caller can
            archive the file that was actually written.
        """
        filename = self.document_filename(url)
        filepath = os.path.join(self.save_path, filename)
        if not os.path.exists(filepath):
            async with session.get(url) as response:
                filename = self.with_content_type_extension(
                    filename, response.headers.get('Content-Type')
                )
                filepath = os.path.join(self.save_path, filename)
                if not os.path.exists(filepath):
                    with open(filepath, 'wb') as file:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            file.write(chunk)
                    print(f'Downloaded {filename}')
        return filename

    async def download_documents(self):
        self.scraper.start_crawling()
        document_urls = self.scraper.get_document_urls()
        async with aiohttp.ClientSession() as session:
            tasks = [self.save_document(session, url) for url in document_urls]
            await asyncio.gather(*tasks)

if __name__ == '__main__':
    # Bounded demo run: the society site links the document paths, the web3
    # front end alone exposes none.
    downloader = DocumentDownloader(
        'https://web3.isss.org',
        'downloaded_documents',
        seed_urls=['https://web3.isss.org', 'https://www.isss.org/annual-meetings/'],
        max_pages=25,
    )
    asyncio.run(downloader.download_documents())

