import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class WebScraper:
    def __init__(self, base_url="https://web3.isss.org"):
        """Initializes the WebScraper with the base URL of the Open ISSS site.
        
        Args:
            base_url (str): The base URL from which the scraping starts. Defaults to Open ISSS site.
        """
        self.base_url = base_url
        self.visited_urls = set()  # Tracks visited URLs to avoid revisiting.
        self.document_urls = []  # Stores discovered document URLs.
        self.total_scraped_pages = 0  # Tracks the total number of pages scraped.
        self.total_documents_found = 0  # Tracks the total number of documents found.

    def is_valid_url(self, url):
        """Checks if a URL is valid and belongs to the specified domain.
        
        Args:
            url (str): The URL to validate.
        
        Returns:
            bool: True if the URL is valid and belongs to the *.isss.org domain, False otherwise.
        """
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme) and parsed.netloc.endswith('isss.org')

    def get_all_links(self, url):
        """Fetches all valid links from a given webpage that belong to the specified domain.
        
        Args:
            url (str): The URL of the webpage to scrape.
        
        Returns:
            list: A list of valid URLs found on the page that belong to the *.isss.org domain.
        """
        urls = []
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)  # Resolve relative URLs.
                if self.is_valid_url(full_url):
                    urls.append(full_url)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
        return urls

    def filter_documents(self, urls):
        """Filters URLs that point to documents based on their extension.
        
        Args:
            urls (list): A list of URLs to filter.
        """
        doc_extensions = ['.pdf', '.docx', '.pptx', '.xlsx']
        for url in urls:
            if any(url.endswith(ext) for ext in doc_extensions) and url not in self.document_urls:
                self.document_urls.append(url)
                self.total_documents_found += 1  # Increment the document count

    def crawl(self, url, depth=0, max_depth=11):
        """Recursively visits URLs within the specified domain and collects document links up to a specified depth.
        
        Args:
            url (str): The URL to start crawling from.
            depth (int): The current depth of the crawl.
            max_depth (int): The maximum depth to crawl.
        """
        if depth > max_depth or url in self.visited_urls:
            return
        print(f"Scraping {url} at depth {depth}")
        self.visited_urls.add(url)
        self.total_scraped_pages += 1  # Increment the page count
        links = self.get_all_links(url)
        self.filter_documents(links)

        for link in links:
            self.crawl(link, depth + 1, max_depth)

    def start_crawling(self):
        """Initiates the crawling process."""
        self.crawl(self.base_url)
        print(f"Scraping completed. Total pages scraped: {self.total_scraped_pages}")
        print(f"Total documents found: {self.total_documents_found}")

    def get_document_urls(self):
        """Returns the list of document URLs found within the specified domain.
        
        Returns:
            list: A list of URLs pointing to documents within the *.isss.org domain.
        """
        return self.document_urls

if __name__ == "__main__":
    base_url = "https://web3.isss.org"  # Example base URL for standalone operation
    scraper = WebScraper(base_url)
    scraper.start_crawling()
    documents = scraper.get_document_urls()
    print(f"Found {len(documents)} documents: ")
    for doc in documents:
        print(doc)
