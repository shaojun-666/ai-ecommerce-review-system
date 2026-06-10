"""Tests for the crawler base class and error types."""
import pytest
from unittest.mock import patch, MagicMock
import requests

from app.crawler.base import (
    BaseCrawler,
    CrawlerError,
    CrawlerTimeoutError,
    CrawlerBlockedError,
    EmptyResponseError,
    ExtractionError,
    PageNotFoundError,
    CrawlerResult,
)


class TestCrawlerErrors:
    def test_crawler_error(self):
        err = CrawlerError("test error")
        assert str(err) == "test error"
        assert isinstance(err, Exception)

    def test_crawler_timeout_error(self):
        err = CrawlerTimeoutError("timeout")
        assert isinstance(err, CrawlerError)

    def test_crawler_blocked_error(self):
        err = CrawlerBlockedError("blocked")
        assert isinstance(err, CrawlerError)

    def test_empty_response_error(self):
        err = EmptyResponseError("empty")
        assert isinstance(err, CrawlerError)

    def test_extraction_error(self):
        err = ExtractionError("parse failed")
        assert isinstance(err, CrawlerError)

    def test_page_not_found_error(self):
        err = PageNotFoundError("404")
        assert isinstance(err, CrawlerError)


class TestCrawlerResult:
    def test_default_fields(self):
        result = CrawlerResult()
        assert result.product is None
        assert result.reviews == []
        assert result.total_pages == 0
        assert result.error is None
        assert result.blocked is False

    def test_with_product(self):
        result = CrawlerResult(product={"name": "test"}, items_found=1)
        assert result.product["name"] == "test"
        assert result.items_found == 1

    def test_with_error(self):
        result = CrawlerResult(error="something went wrong", blocked=True)
        assert result.error == "something went wrong"
        assert result.blocked is True


class TestBaseCrawler:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseCrawler()

    def test_concrete_crawler_requires_methods(self):
        class MinimalCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {"name": "test"}

            def extract_reviews(self, url, html, page=1):
                return [{"content": "ok"}]

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

        crawler = MinimalCrawler(platform="test")
        assert crawler.platform == "test"
        assert crawler.max_retries == 3
        assert crawler.retry_base_delay == 2.0

    def test_crawl_product_success(self):
        class TestCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {"name": "Test Product", "price": 99.0}

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return "<html>test</html>"

        crawler = TestCrawler(platform="test")
        result = crawler.crawl_product("https://example.com/product/1")
        assert result.product is not None
        assert result.product["name"] == "Test Product"
        assert result.error is None

    def test_crawl_product_fetch_failure(self):
        class FailingCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {"name": "test"}

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return None

        crawler = FailingCrawler(platform="test")
        result = crawler.crawl_product("https://example.com/product/1")
        assert result.product is None
        assert result.error is not None

    def test_crawl_product_extraction_failure(self):
        class BrokenCrawler(BaseCrawler):
            def extract_product(self, url, html):
                raise ExtractionError("Field missing")

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return "<html>test</html>"

        crawler = BrokenCrawler(platform="test")
        result = crawler.crawl_product("https://example.com/product/1")
        assert result.product is None
        assert "Field missing" in result.error

    def test_crawl_reviews_empty_html(self):
        class EmptyCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {}

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return None

        crawler = EmptyCrawler(platform="test")
        result = crawler.crawl_reviews("https://example.com/product/1", page=1)
        assert result.error is not None
        assert result.current_page == 1

    def test_crawl_reviews_success(self):
        class TestCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {}

            def extract_reviews(self, url, html, page=1):
                return [{"content": f"review {page}"}]

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return "<html>test</html>"

        crawler = TestCrawler(platform="test")
        result = crawler.crawl_reviews("https://example.com/product/1", page=1)
        assert len(result.reviews) == 1
        assert result.items_found == 1

    def test_crawl_all_aggregates_pages(self):
        class TestCrawler(BaseCrawler):
            def __init__(self):
                super().__init__(platform="test")
                self.call_count = 0

            def extract_product(self, url, html):
                return {"name": "p1"}

            def extract_reviews(self, url, html, page=1):
                self.call_count += 1
                return [{"content": f"r{page}_{i}"} for i in range(10)]

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return "<html>test</html>"

        crawler = TestCrawler()
        result = crawler.crawl_all("https://example.com/p1", page_limit=3)
        assert result.product["name"] == "p1"
        assert len(result.reviews) == 30
        assert result.items_found == 30

    def test_crawl_all_stops_on_error(self):
        class ErrorCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {"name": "p1"}

            def extract_reviews(self, url, html, page=1):
                if page == 1:
                    raise ExtractionError("parse error")
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

            def _fetch_with_retry(self, url):
                return "<html>test</html>"

        crawler = ErrorCrawler(platform="test")
        result = crawler.crawl_all("https://example.com/p1", page_limit=3)
        assert result.error is not None
        assert result.product is not None  # product still extracted

    def test_fetch_with_retry_blocked_error(self):
        """Verify that CrawlerBlockedError is raised after exhausting retries."""
        crawler = None

        class BlockedCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {}

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

        crawler = BlockedCrawler(platform="test", max_retries=2)
        crawler.anti_bot.get = MagicMock()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"captcha"
        mock_resp.text = "captcha"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.ok = True
        crawler.anti_bot.get.return_value = mock_resp

        with pytest.raises(CrawlerBlockedError):
            crawler._fetch_with_retry("https://example.com")

    def test_fetch_with_retry_404(self):
        class NotFoundCrawler(BaseCrawler):
            def extract_product(self, url, html):
                return {}

            def extract_reviews(self, url, html, page=1):
                return []

            def get_review_url(self, product_url, page=1):
                return f"{product_url}/reviews/{page}"

        crawler = NotFoundCrawler(platform="test")
        crawler.anti_bot.get = MagicMock()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 404
        mock_resp.text = ""
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.ok = False
        crawler.anti_bot.get.return_value = mock_resp

        with pytest.raises(PageNotFoundError):
            crawler._fetch_with_retry("https://example.com/404")
