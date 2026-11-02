from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class WebScraper:
    def __init__(self, base_url="https://web3.isss.org", seed_urls=None, max_pages=None):
        """Initializes the WebScraper with the pages to start crawling from.
        
        Args:
            base_url (str): The base URL of the Open ISSS site. Defaults to Open ISSS site.
            seed_urls (list): Pages the crawl starts from. Defaults to ``[base_url]``.
            max_pages (int): Optional upper bound on pages fetched in one run.
                Defaults to None, which leaves the crawl unbounded.
        """
        self.base_url = base_url
        self.seed_urls = list(seed_urls) if seed_urls else [base_url]
        self.max_pages = max_pages
        self.visited_urls = set()  # Tracks visited URLs to avoid revisiting.
        self.document_urls = []  # Stores discovered document URLs.
        self.total_scraped_pages = 0  # Tracks the total number of pages scraped.
        self.total_documents_found = 0  # Tracks the total number of documents found.

    def _page_budget_exhausted(self):
        """Checks whether the optional page budget for this run is used up.

        Returns:
            bool: True when ``max_pages`` is set and reached, False otherwise.
        """
        return self.max_pages is not None and self.total_scraped_pages >= self.max_pages

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
            response = requests.get(url, timeout=30)
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

        Returns:
            None: Appends matching URLs to self.document_urls in place.
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
        if depth > max_depth or url in self.visited_urls or self._page_budget_exhausted():
            return
        print(f"Scraping {url} at depth {depth}")
        self.visited_urls.add(url)
        self.total_scraped_pages += 1  # Increment the page count
        links = self.get_all_links(url)
        self.filter_documents(links)

        for link in links:
            self.crawl(link, depth + 1, max_depth)

    def start_crawling(self, max_depth=11):
        """Initiates the crawling process from every configured seed page.

        Args:
            max_depth (int): The maximum depth to crawl from each seed.
        """
        print(f"Starting crawl from {len(self.seed_urls)} seed page(s).")
        for seed_url in self.seed_urls:
            self.crawl(seed_url, 0, max_depth)
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
    # The web3 front end alone exposes no documents; the society site links them.
    seed_urls = [base_url, "https://www.isss.org/annual-meetings/"]
    scraper = WebScraper(base_url, seed_urls=seed_urls, max_pages=25)
    scraper.start_crawling()
    documents = scraper.get_document_urls()
    print(f"Found {len(documents)} documents: ")
    for doc in documents:
        print(doc)
