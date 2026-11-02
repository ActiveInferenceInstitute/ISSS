"""Tests for ``web_scraper.WebScraper`` — seeds, filtering, depth and budget."""

import requests

from web_scraper import WebScraper


def test_seed_urls_default_to_the_base_url():
    scraper = WebScraper("https://web3.isss.org")
    assert scraper.seed_urls == ["https://web3.isss.org"]
    assert scraper.max_pages is None


def test_is_valid_url_accepts_the_isss_domains_only():
    scraper = WebScraper()
    assert scraper.is_valid_url("https://web3.isss.org/proceedings/x.pdf")
    assert scraper.is_valid_url("https://www.isss.org/annual-meetings/")
    assert not scraper.is_valid_url("https://example.org/x.pdf")
    assert not scraper.is_valid_url("mailto:someone@isss.org")
    assert not scraper.is_valid_url("not-a-url")


def test_filter_documents_keeps_supported_extensions_without_duplicates():
    scraper = WebScraper()
    scraper.filter_documents(
        [
            "https://web3.isss.org/a.pdf",
            "https://web3.isss.org/b.docx",
            "https://web3.isss.org/c.pptx",
            "https://web3.isss.org/d.xlsx",
            "https://web3.isss.org/page.html",
            "https://web3.isss.org/a.pdf",
        ]
    )
    assert scraper.get_document_urls() == [
        "https://web3.isss.org/a.pdf",
        "https://web3.isss.org/b.docx",
        "https://web3.isss.org/c.pptx",
        "https://web3.isss.org/d.xlsx",
    ]
    assert scraper.total_documents_found == 4


def test_crawl_visits_every_seed_and_collects_linked_documents(fixture_site, local_scraper):
    fixture_site.page(
        "/annual-meetings/",
        links=[
            "/editor_upload/programme.pdf",
            "https://example.org/not-isss.pdf",
        ],
    )
    fixture_site.page("/conference/", links=["/editor_upload/template.docx"])
    fixture_site.page("/editor_upload/programme.pdf")

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[
            f"{fixture_site.base_url}/annual-meetings/",
            f"{fixture_site.base_url}/conference/",
        ],
    )
    scraper.start_crawling(max_depth=1)

    assert scraper.get_document_urls() == [
        f"{fixture_site.base_url}/editor_upload/programme.pdf",
        f"{fixture_site.base_url}/editor_upload/template.docx",
    ]
    assert {"/annual-meetings/", "/conference/"} <= set(fixture_site.requested_paths)


def test_crawl_honours_max_depth(fixture_site, local_scraper):
    fixture_site.page("/seed/", links=["/level-1/"])
    fixture_site.page("/level-1/", links=["/level-2/"])

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
    )
    scraper.start_crawling(max_depth=0)

    assert scraper.total_scraped_pages == 1
    assert fixture_site.requested_paths == ["/seed/"]


def test_page_budget_stops_the_crawl(fixture_site, local_scraper):
    fixture_site.page("/seed/", links=["/a/", "/b/", "/c/"])
    for path in ("/a/", "/b/", "/c/"):
        fixture_site.page(path)

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
        max_pages=2,
    )
    scraper.start_crawling(max_depth=2)

    assert scraper.total_scraped_pages == 2
    assert len(fixture_site.requested_paths) == 2


def test_unreachable_page_is_reported_and_the_crawl_continues(
    fixture_site, local_scraper, monkeypatch, capsys
):
    fixture_site.page("/seed/", links=["/broken/", "/ok/"])
    fixture_site.page("/ok/", links=["/editor_upload/kept.pdf"])

    original_get = requests.get

    def flaky_get(url, **kwargs):
        if url.endswith("/broken/"):
            raise requests.exceptions.ConnectionError("simulated failure")
        return original_get(url, **kwargs)

    monkeypatch.setattr(requests, "get", flaky_get)

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
    )
    scraper.start_crawling(max_depth=1)

    assert "simulated failure" in capsys.readouterr().out
    assert scraper.get_document_urls() == [f"{fixture_site.base_url}/editor_upload/kept.pdf"]
