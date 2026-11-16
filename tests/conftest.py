"""Shared fixtures for the ISSS test suite.

Every test runs offline against local fixtures: no test performs a live network
request, and none requires the system Tesseract binary (the OCR test replaces
``pytesseract.image_to_string`` with a stub).
"""

import http.server
import shutil
import socket
import threading
from pathlib import Path
from typing import ClassVar

import pytest

from document_downloader import DownloadReceipt
from pipeline_artifacts import ArtifactStore, file_identity
from web_scraper import WebScraper


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch):
    """Fails any test that opens a socket to a host other than loopback.

    The suite must stay offline: the only permitted connections are the ones to
    the in-process fixture server on 127.0.0.1.
    """
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and not (
            host.startswith("127.") or host in {"localhost", "::1", "0.0.0.0"}
        ):
            raise AssertionError(f"test attempted a live network connection to {host}")
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    """Serves the pages registered on ``pages``; unknown paths return 404."""

    pages: ClassVar[dict] = {}
    requested_paths: ClassVar[list] = []

    def do_GET(self):
        type(self).requested_paths.append(self.path)
        body = type(self).pages.get(self.path)
        if body is None:
            self.send_error(404)
            return
        payload = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        """Keeps the test output free of per-request log lines."""


class _Site:
    """Registers fixture pages and reports which paths were requested."""

    def __init__(self, port):
        self.base_url = f"http://127.0.0.1:{port}"

    def add(self, path, html):
        _FixtureHandler.pages[path] = html

    def page(self, path, links=(), text="fixture page"):
        """Registers a page whose body links to the given paths."""
        anchors = "".join(f'<a href="{href}">{href}</a>' for href in links)
        self.add(path, f"<html><body><p>{text}</p>{anchors}</body></html>")

    @property
    def requested_paths(self):
        return list(_FixtureHandler.requested_paths)


@pytest.fixture
def fixture_site():
    """Runs a local HTTP server for the duration of one test."""
    _FixtureHandler.pages = {}
    _FixtureHandler.requested_paths = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Site(server.server_port)
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def local_scraper():
    """A ``WebScraper`` that accepts the fixture host in addition to *.isss.org."""

    class LocalWebScraper(WebScraper):
        def is_valid_url(self, url):
            return "127.0.0.1" in url or super().is_valid_url(url)

    return LocalWebScraper


@pytest.fixture
def receipt_factory(tmp_path):
    """Write actual fixture bytes and bind a deterministic acquisition receipt."""
    def create(name='paper.pdf', payload=b'fixture', url=None, acquired=None):
        path = tmp_path / 'downloaded_documents' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        source_url = url or f'https://web3.isss.org/{name}'
        return DownloadReceipt(
            source_url, source_url, name, str(path), **file_identity(path),
            download_date=acquired or '2020-01-02T03:04:05+00:00',
        )
    return create


@pytest.fixture
def publish_conversion(tmp_path):
    """Publish real fixture text/images through the same immutable-set protocol."""
    def publish(name='paper.pdf', text='fixture', pages=()):
        root = tmp_path / 'converted_documents'
        source = tmp_path / 'fixture_sources' / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(text.encode('utf-8') + b'\0' + b''.join(
            Path(page).read_bytes() for page in pages
        ))
        store = ArtifactStore(root, 'conversion')
        with store.stage() as (generation, staged):
            (staged / 'text').mkdir()
            text_name = Path(name).stem + '.txt'
            (staged / 'text' / text_name).write_text(text, encoding='utf-8')
            (staged / 'pages').mkdir()
            prefix = f'.generations/{generation}/'
            page_files = []
            for number, page in enumerate(pages, 1):
                relative = f'pages/page-{number:04d}.png'
                shutil.copyfile(page, staged / relative)
                page_files.append(prefix + relative)
            record = store.publish(staged, {
                'document_name': name, 'generation': generation,
                'source': {'path': str(source), **file_identity(source)},
                'text_file': prefix + 'text/' + text_name,
                'page_files': page_files, 'page_count': len(page_files),
                'characters': len(text),
            })
        store.commit()
        return root, record
    return publish
