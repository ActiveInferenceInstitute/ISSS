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


def test_normalise_url_strips_fragments_sessions_and_default_ports():
    assert WebScraper.normalise_url("https://web3.isss.org/#content") == "https://web3.isss.org/"
    assert WebScraper.normalise_url(
        "HTTPS://Web3.ISSS.org:443/a/?utm_source=x&sid=1&q=2#top"
    ) == "https://web3.isss.org/a/?q=2"
    assert WebScraper.normalise_url("http://www.isss.org:80/a") == "http://www.isss.org/a"
    # A query string that identifies the resource is kept.
    assert WebScraper.normalise_url(
        "https://journals.isss.org/article/download/1766/611/7584?download=1"
    ) == "https://journals.isss.org/article/download/1766/611/7584?download=1"
    assert WebScraper.normalise_url("mailto:someone@isss.org") == ""


def test_crawl_works_from_a_single_url(fixture_site, local_scraper):
    """The single-URL entry point keeps working alongside ``start_crawling``."""
    fixture_site.page("/seed/", links=["/editor_upload/solo.pdf"])

    scraper = local_scraper("https://web3.isss.org")
    scraper.crawl(f"{fixture_site.base_url}/seed/", max_depth=1)

    assert scraper.total_scraped_pages == 1
    assert scraper.get_document_urls() == [f"{fixture_site.base_url}/editor_upload/solo.pdf"]


def test_crawl_ignores_a_url_it_cannot_fetch(local_scraper):
    scraper = local_scraper("https://web3.isss.org")

    scraper.crawl("mailto:someone@isss.org")

    assert scraper.total_scraped_pages == 0
    assert not scraper.visited_urls


def test_max_pages_holds_even_with_seeds_left(fixture_site, local_scraper):
    fixture_site.page("/one/", links=["/one/2/"])
    fixture_site.page("/two/", links=["/editor_upload/two.pdf"])

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/one/", f"{fixture_site.base_url}/two/"],
        max_pages=1,
    )
    scraper.start_crawling(max_depth=2)

    assert fixture_site.requested_paths == ["/one/"]
    assert scraper.total_scraped_pages == 1
    assert scraper.get_document_urls() == []


def test_is_crawl_utility_covers_site_machinery_only():
    assert WebScraper.is_crawl_utility("https://www.isss.org/wp-login.php")
    assert WebScraper.is_crawl_utility("https://www.isss.org/wp-admin/options.php")
    assert WebScraper.is_crawl_utility("https://www.isss.org/?s=active+inference")
    assert WebScraper.is_crawl_utility("https://www.isss.org/annual-meetings/feed/")
    assert WebScraper.is_crawl_utility("https://www.isss.org/2025/reply/?replytocom=7")
    assert not WebScraper.is_crawl_utility("https://www.isss.org/annual-meetings/")
    assert not WebScraper.is_crawl_utility(
        "https://www.isss.org/wp-content/uploads/2025/proceedings.pdf"
    )
    assert not WebScraper.is_crawl_utility("https://www.isss.org/editor_upload/search-protocol/")
    assert not WebScraper.is_crawl_utility("https://www.isss.org/annual-meetings/?paged=2")


def test_fragment_links_do_not_refetch_the_same_page(fixture_site, local_scraper):
    """``#content`` and ``#respond`` links point at the page they sit on."""
    fixture_site.page("/seed/", links=["#content", "/seed/#respond", "/a/"])
    fixture_site.page("/a/")

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
    )
    scraper.start_crawling(max_depth=1)

    assert fixture_site.requested_paths == ["/seed/", "/a/"]
    assert scraper.total_scraped_pages == 2


def test_utility_pages_spend_no_budget(fixture_site, local_scraper):
    fixture_site.page(
        "/seed/",
        links=[
            "#content",
            "/wp-login.php",
            "/wp-admin/",
            "/feed/",
            "/?s=inference",
            "/wp-json/wp/v2/pages",
            "/comments/feed/",
            "/search/",
        ],
    )

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
    )
    scraper.start_crawling(max_depth=2)

    assert fixture_site.requested_paths == ["/seed/"]
    assert scraper.total_scraped_pages == 1


def test_document_links_are_recorded_without_being_fetched(fixture_site, local_scraper):
    """A PDF is a result, not a page to crawl: fetching it only spends budget."""
    fixture_site.page("/seed/", links=["/editor_upload/report.pdf"])

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed/"],
    )
    scraper.start_crawling(max_depth=2)

    assert scraper.get_document_urls() == [f"{fixture_site.base_url}/editor_upload/report.pdf"]
    assert fixture_site.requested_paths == ["/seed/"]


def test_seeds_take_turns_so_the_first_cannot_starve_the_rest(fixture_site, local_scraper):
    fixture_site.page("/one/", links=["/one/2/", "/one/3/"])
    fixture_site.page("/one/2/", links=["/one/4/"])
    fixture_site.page("/one/3/")
    fixture_site.page("/one/4/")
    fixture_site.page("/two/", links=["/editor_upload/two.pdf"])

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/one/", f"{fixture_site.base_url}/two/"],
        max_pages=2,
    )
    scraper.start_crawling(max_depth=2)

    # Two pages of budget, one turn each: the first seed gets one, not both.
    assert fixture_site.requested_paths == ["/one/", "/two/"]
    assert scraper.get_document_urls() == [f"{fixture_site.base_url}/editor_upload/two.pdf"]


def test_a_small_budget_still_reaches_the_second_seed(fixture_site, local_scraper):
    """Link furniture used to eat the budget before the second seed was reached."""
    fixture_site.page(
        "/seed-one/",
        links=["#content", "/wp-login.php", "/?s=inference", "/a/", "/b/"],
    )
    fixture_site.page("/a/", links=["/c/"])
    fixture_site.page("/b/")
    fixture_site.page("/c/")
    fixture_site.page("/seed-two/", links=["/editor_upload/second.pdf"])

    scraper = local_scraper(
        "https://web3.isss.org",
        seed_urls=[f"{fixture_site.base_url}/seed-one/", f"{fixture_site.base_url}/seed-two/"],
        max_pages=3,
    )
    scraper.start_crawling(max_depth=1)

    assert "/seed-two/" in fixture_site.requested_paths
    assert scraper.get_document_urls() == [f"{fixture_site.base_url}/editor_upload/second.pdf"]
    assert scraper.total_scraped_pages == 3

