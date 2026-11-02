from collections import deque
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

#: Document extensions the pipeline converts.
DOCUMENT_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx')
#: Path segments that mark crawl utilities: they never carry documents.
UTILITY_PATH_SEGMENTS = (
    'wp-admin',
    'wp-login.php',
    'wp-signup.php',
    'wp-register.php',
    'wp-cron.php',
    'wp-json',
    'xmlrpc.php',
    'feed',
    'comments',
    'search',
)
#: Query keys that mark a search, feed or reply page rather than content.
UTILITY_QUERY_KEYS = ('s', 'feed', 'replytocom')
#: Query keys that carry session or tracking state; they are dropped from the URL.
TRACKING_QUERY_KEYS = ('sid', 'sessionid', 'phpsessid', 'jsessionid', 'fbclid', 'gclid')


class WebScraper:
    def __init__(self, base_url="https://web3.isss.org", seed_urls=None, max_pages=None):
        """Initializes the WebScraper with the pages to start crawling from.
        
        Args:
            base_url (str): The base URL of the Open ISSS site. Defaults to Open ISSS site.
            seed_urls (list): Pages the crawl starts from. Defaults to ``[base_url]``.
            max_pages (int): Optional upper bound on the total number of pages
                fetched in one run, across every seed. Defaults to None, which
                leaves the crawl unbounded.
        """
        self.base_url = base_url
        self.seed_urls = list(seed_urls) if seed_urls else [base_url]
        self.max_pages = max_pages
        self.visited_urls = set()  # Tracks visited URLs to avoid revisiting.
        self.queued_urls = set()  # Tracks queued URLs to avoid duplicate fetches.
        self.document_urls = []  # Stores discovered document URLs.
        self.total_scraped_pages = 0  # Tracks the total number of pages scraped.
        self.total_documents_found = 0  # Tracks the total number of documents found.

    def _page_budget_exhausted(self):
        """Checks whether the optional page budget for this run is used up.

        Returns:
            bool: True when ``max_pages`` is set and reached, False otherwise.
        """
        return self.max_pages is not None and self.total_scraped_pages >= self.max_pages

    @staticmethod
    def normalise_url(url):
        """Returns the canonical form of a crawl URL.

        The fragment is dropped, the scheme and host are lowercased, a default
        port and the session and tracking parameters are removed, and an empty
        query disappears. Links that differ only in those parts therefore become
        one URL, so the page behind them is fetched once instead of once per
        fragment.

        Args:
            url (str): The URL to normalise.

        Returns:
            str: The canonical URL, or ``''`` when the URL has no scheme or host
            and cannot be fetched.
        """
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ''
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith('utm_')
        ]
        netloc = parsed.netloc.lower()
        if netloc.endswith(':80') and parsed.scheme.lower() == 'http':
            netloc = netloc[: -len(':80')]
        elif netloc.endswith(':443') and parsed.scheme.lower() == 'https':
            netloc = netloc[: -len(':443')]
        return urlunparse(
            (parsed.scheme.lower(), netloc, parsed.path or '/', '', urlencode(query), '')
        )

    @staticmethod
    def is_document_url(url):
        """Checks whether a URL points to a document the pipeline converts.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True when the URL's path ends with a supported extension.
        """
        return urlparse(url).path.lower().endswith(DOCUMENT_EXTENSIONS)

    @staticmethod
    def is_crawl_utility(url):
        """Checks whether a URL is site machinery rather than a content page.

        Login, admin, feed, search, reply and REST endpoints bring no documents
        of their own, so fetching them only spends the page budget.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True when a path segment or a query key marks a crawl utility.
        """
        parsed = urlparse(url)
        segments = [segment.lower() for segment in parsed.path.split('/') if segment]
        if any(segment in UTILITY_PATH_SEGMENTS for segment in segments):
            return True
        keys = [key.lower() for key, _value in parse_qsl(parsed.query, keep_blank_values=True)]
        return any(key in UTILITY_QUERY_KEYS for key in keys)

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
        """Records the document URLs among ``urls``, normalised and deduplicated.

        A link whose fragment differs from an earlier one points at the same
        file, so normalization happens before the extension test: without it a
        ``report.pdf#page=2`` link would be missed.

        Args:
            urls (list): A list of URLs to filter.

        Returns:
            None: Appends matching URLs to self.document_urls in place.
        """
        for url in urls:
            candidate = self.normalise_url(url)
            if not candidate or candidate in self.document_urls:
                continue
            if self.is_document_url(candidate):
                self.document_urls.append(candidate)
                self.total_documents_found += 1  # Increment the document count

    def _visit(self, url, depth, queue, max_depth):
        """Fetches one page, records its documents and queues its crawl links.

        Args:
            url (str): The normalised URL of the page to fetch.
            depth (int): The depth of this page below its seed.
            queue (deque): The seed's queue, which the page's links are added to.
            max_depth (int): The maximum depth to crawl.
        """
        print(f"Scraping {url} at depth {depth}")
        self.visited_urls.add(url)
        self.total_scraped_pages += 1  # Increment the page count
        links = self.get_all_links(url)
        self.filter_documents(links)
        if depth >= max_depth:
            return
        for link in links:
            candidate = self.normalise_url(link)
            if not candidate or candidate in self.visited_urls or candidate in self.queued_urls:
                continue
            if self.is_document_url(candidate) or self.is_crawl_utility(candidate):
                continue
            queue.append((candidate, depth + 1))
            self.queued_urls.add(candidate)

    def _crawl_queues(self, queues, max_depth):
        """Fetches one page per queue per pass until the queues or budget run out.

        Each queue belongs to one seed, so giving every non-empty queue a turn
        before any queue gets a second one keeps one seed from spending the
        whole budget. A queue whose links are exhausted drops out and the
        remaining seeds continue without it.

        Args:
            queues (list): One ``deque`` of ``(url, depth)`` pairs per seed.
            max_depth (int): The maximum depth to crawl from each seed.
        """
        while not self._page_budget_exhausted():
            progressed = False
            for queue in queues:
                if not queue:
                    continue
                if self._page_budget_exhausted():
                    break
                url, depth = queue.popleft()
                self._visit(url, depth, queue, max_depth)
                progressed = True
            if not progressed:
                break

    def crawl(self, url, depth=0, max_depth=11):
        """Crawls from one URL, spending the whole remaining budget on it.

        ``start_crawling`` is the form the pipeline uses; this entry point keeps
        the single-URL call and shares its queue machinery, so one seed crawls
        breadth-first from ``url``.

        Args:
            url (str): The URL to start crawling from.
            depth (int): The current depth of the crawl.
            max_depth (int): The maximum depth to crawl.
        """
        seed = self.normalise_url(url)
        if not seed:
            return
        self.queued_urls.add(seed)
        self._crawl_queues([deque([(seed, depth)])], max_depth)

    def start_crawling(self, max_depth=11):
        """Crawls every configured seed page until the links or budget run out.

        Seed pages take turns one page at a time (round-robin), so the first
        seed cannot spend the whole budget before the others are reached; a seed
        whose links are exhausted drops out. ``max_pages`` is the total page
        budget for the run, across all seeds, unchanged from earlier runs.

        Args:
            max_depth (int): The maximum depth to crawl from each seed.
        """
        print(f"Starting crawl from {len(self.seed_urls)} seed page(s).")
        queues = []
        for seed_url in self.seed_urls:
            queue = deque()
            seed = self.normalise_url(seed_url)
            if seed and seed not in self.queued_urls:
                queue.append((seed, 0))
                self.queued_urls.add(seed)
            queues.append(queue)
        self._crawl_queues(queues, max_depth)
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
