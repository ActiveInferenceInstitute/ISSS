"""Shared fixtures for the ISSS test suite.

Every test runs offline against local fixtures: no test performs a live network
request, and none requires the system Tesseract binary (the OCR test replaces
``pytesseract.image_to_string`` with a stub).
"""

import http.server
import socket
import threading
from typing import ClassVar

import pytest

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
