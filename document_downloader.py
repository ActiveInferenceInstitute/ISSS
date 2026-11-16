"""HTTP-admitted downloads with atomic bytes and source-bound acquisition receipts."""

import asyncio
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import aiohttp

from pipeline_artifacts import atomic_json, file_identity
from web_scraper import WebScraper

#: Document extensions the later stages convert.
DOCUMENT_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx')
#: Extension to use when the URL path carries none but the content type does.
CONTENT_TYPE_EXTENSIONS = {
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
}


class DownloadError(RuntimeError):
    """A download or provenance admission failed; existing bytes are preserved."""


@dataclass(frozen=True)
class DownloadReceipt:
    source_url: str
    final_url: str
    document_name: str
    document_path: str
    sha256: str
    size: int
    download_date: str
    cached: bool = False

    def validate(self):
        """Admit only an actual completed file with a qualified acquisition time."""
        if Path(self.document_path).name != self.document_name:
            raise DownloadError('receipt filename/path mismatch')
        if not WebScraper.is_valid_url(self.source_url) or not WebScraper.is_valid_url(
            self.final_url
        ):
            raise DownloadError('receipt source is outside the ISSS HTTP boundary')
        acquired = datetime.fromisoformat(self.download_date)
        if acquired.tzinfo is None:
            raise DownloadError('receipt acquisition time must include a timezone')
        if type(self.size) is not int or self.size < 0:
            raise DownloadError('invalid receipt byte count')
        if file_identity(self.document_path) != {'sha256': self.sha256, 'size': self.size}:
            raise DownloadError('receipt content does not match the document')
        return self


class DocumentDownloader:
    def __init__(self, base_url, save_path, seed_urls=None, max_pages=None):
        self.base_url = base_url
        self.save_path = str(Path(save_path).absolute())
        if Path(self.save_path).is_symlink():
            raise DownloadError('download directory must not be a symlink')
        Path(self.save_path).mkdir(parents=True, exist_ok=True)
        self.scraper = WebScraper(base_url, seed_urls=seed_urls, max_pages=max_pages)
        self._url_locks = {}
        self._file_locks = {}

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

    def _receipt_path(self, url):
        directory = Path(self.save_path) / '.receipts'
        if directory.is_symlink():
            raise DownloadError('receipt directory must not be a symlink')
        return directory / (hashlib.sha256(url.encode('utf-8')).hexdigest() + '.json')

    def _cached_receipt(self, url):
        path = self._receipt_path(url)
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink():
            raise DownloadError('receipt must not be a symlink')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.pop('schema', None) != 'isss-download/v1':
            raise DownloadError('invalid download receipt')
        receipt = DownloadReceipt(**data).validate()
        expected_path = str(Path(self.save_path) / receipt.document_name)
        if receipt.source_url != url or receipt.document_path != expected_path:
            raise DownloadError('receipt source/path mismatch')
        return replace(receipt, cached=True)

    async def save_document(self, session, url):
        """Return a qualified receipt, never infer completion from file existence."""
        if not WebScraper.is_valid_url(url):
            raise DownloadError(f'disallowed document URL: {url}')
        url = urlsplit(url)._replace(fragment='').geturl()
        lock = self._url_locks.setdefault(url, asyncio.Lock())
        async with lock:
            try:
                cached = self._cached_receipt(url)
                if cached is not None:
                    return cached
                return await self._fetch_document(session, url)
            except (OSError, ValueError, TypeError, aiohttp.ClientError) as error:
                raise DownloadError(str(error)) from error

    async def _fetch_document(self, session, url):
        current = url
        for _ in range(11):
            if not WebScraper.is_valid_url(current):
                raise DownloadError(f'disallowed redirect: {current}')
            async with session.get(current, allow_redirects=False) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get('Location')
                    if not location:
                        raise DownloadError('redirect has no Location')
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                if not 200 <= response.status < 300:
                    raise DownloadError(f'HTTP status {response.status}')
                filename = self.with_content_type_extension(
                    self.document_filename(url), response.headers.get('Content-Type')
                )
                if filename in {'.', '..'} or '\x00' in filename:
                    raise DownloadError('unsafe document filename')
                target = Path(self.save_path) / filename
                lock = self._file_locks.setdefault(filename, asyncio.Lock())
                async with lock:
                    if target.exists() or target.is_symlink():
                        raise DownloadError(f'ambiguous existing document preserved: {filename}')
                    return await self._publish_response(response, url, current, target)
        raise DownloadError('too many redirects')

    async def _publish_response(self, response, source_url, final_url, target):
        descriptor, temporary = tempfile.mkstemp(prefix='.download-', dir=self.save_path)
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                while True:
                    chunk = await response.content.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            receipt = DownloadReceipt(
                source_url, final_url, target.name, str(target),
                digest.hexdigest(), size, datetime.now(timezone.utc).isoformat()
            )
            # No-clobber publication also protects against another process creating
            # an unqualified file after our existence check.
            os.link(temporary, target)
            atomic_json(self._receipt_path(source_url), {
                'schema': 'isss-download/v1', **asdict(receipt)
            })
            print(f'Downloaded {target.name}')
            return receipt
        finally:
            os.unlink(temporary)

    async def download_urls(self, session, urls):
        """Preserve successful peers while reporting each failed acquisition."""
        urls = tuple(urls)
        results = await asyncio.gather(
            *(self.save_document(session, url) for url in urls), return_exceptions=True
        )
        receipts, failures = [], []
        for url, result in zip(urls, results):
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result
                failures.append({'source_url': url, 'error': str(result)})
            else:
                receipts.append(result)
        return receipts, failures

    async def download_documents(self):
        discovery = self.scraper.start_crawling()
        async with aiohttp.ClientSession() as session:
            receipts, failures = await self.download_urls(session, discovery.document_urls)
        return {'discovery': discovery, 'receipts': receipts, 'failures': failures}

if __name__ == '__main__':
    # Bounded demo run: the society site links the document paths, the web3
    # front end alone exposes none.
    downloader = DocumentDownloader(
        'https://web3.isss.org',
        'downloaded_documents',
        seed_urls=['https://web3.isss.org', 'https://www.isss.org/annual-meetings/'],
        max_pages=25,
    )
    result = asyncio.run(downloader.download_documents())
    discovery = result['discovery']
    print(f'Download discovery {discovery.status}; {len(result["receipts"])} qualified receipt(s).')
    for failure in result['failures']:
        print(f'Download failed: {failure["source_url"]}: {failure["error"]}')
    raise SystemExit(1 if discovery.status in {'failed', 'partial'} or result['failures'] else 0)

