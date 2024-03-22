import os
import aiohttp
import asyncio
from web_scraper import WebScraper  # Import the WebScraper class

class DocumentDownloader:
    def __init__(self, base_url, save_path):
        self.base_url = base_url
        self.save_path = save_path
        # Ensure the save path exists
        os.makedirs(save_path, exist_ok=True)
        # Initialize the WebScraper
        self.scraper = WebScraper(base_url)

    async def save_document(self, session, url):
        filename = url.split('/')[-1]
        filepath = os.path.join(self.save_path, filename)
        if not os.path.exists(filepath):
            async with session.get(url) as response:
                with open(filepath, 'wb') as file:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        file.write(chunk)
            print(f'Downloaded {filename}')

    async def download_documents(self):
        self.scraper.start_crawling()
        document_urls = self.scraper.get_document_urls()
        pdf_urls = [url for url in document_urls if url.endswith('.pdf')]
        async with aiohttp.ClientSession() as session:
            tasks = [self.save_document(session, url) for url in pdf_urls]
            await asyncio.gather(*tasks)

if __name__ == '__main__':
    downloader = DocumentDownloader('http://example.com', 'downloaded_documents')
    asyncio.run(downloader.download_documents())

