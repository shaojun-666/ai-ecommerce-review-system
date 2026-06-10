"""Tests for the JD.com crawler adapter.

Uses inline HTML/JSONP fixtures to test extraction logic without network access.
"""
import json
import pytest

from app.crawler.base import ExtractionError
from app.crawler.adapters.jd import (
    JDCrawler,
    _parse_product_id,
    _clean_jsonp,
)

# Minimal JD product detail HTML fixture
_PRODUCT_HTML = """
<html>
<head><title>测试商品名称【京东】</title></head>
<body>
  <div class="sku-name">测试商品名称 2024款</div>
  <span class="p-price">¥299.00</span>
  <div id="spec-img"><img src="https://img.example.com/pic.jpg" /></div>
  <div class="J-hove-wrap"><div class="name"><a>测试旗舰店</a></div></div>
</body>
</html>
"""

# Review JSONP fixture (4 comments)
_REVIEW_JSONP = """fetchJSON_comment98vv123456({
  "comments": [
    {"id": 1, "content": "好评，质量很好", "creationTime": "2024-01-15", "score": 5, "nickname": "用户A", "productColor": "黑色", "productSize": "L"},
    {"id": 2, "content": "一般般吧", "creationTime": "2024-01-14", "score": 3, "nickname": "用户B", "productColor": "白色"},
    {"id": 3, "content": "差评，质量太差", "creationTime": "2024-01-13", "score": 1, "nickname": "用户C"},
    {"id": 4, "content": "", "creationTime": "2024-01-12", "score": 5, "nickname": "用户D"}
  ],
  "productCommentSummary": {"commentCountStr": "1.2万+", "averageScore": 4.8, "maxPage": 50}
})"""

# Empty review page
_EMPTY_REVIEW_JSONP = "fetchJSON_comment98vv999999({\"comments\": [], \"productCommentSummary\": {\"maxPage\": 0}})"


class TestJDCrawlerUtility:
    def test_parse_product_id_full_url(self):
        assert _parse_product_id("https://item.jd.com/123456.html") == "123456"

    def test_parse_product_id_with_hash(self):
        assert _parse_product_id("https://item.jd.com/123456.html#crumb") == "123456"

    def test_parse_product_id_no_match(self):
        assert _parse_product_id("https://example.com") is None

    def test_clean_jsonp_removes_wrapper(self):
        raw = 'callback({"key": "value"})'
        result = _clean_jsonp(raw)
        assert result == '{"key": "value"}'

    def test_clean_jsonp_already_json(self):
        raw = '{"key": "value"}'
        result = _clean_jsonp(raw)
        assert result == '{"key": "value"}'

    def test_clean_jsonp_empty(self):
        assert _clean_jsonp("") == ""


class TestJDCrawlerProduct:
    def setup_method(self):
        self.crawler = JDCrawler()

    def test_extract_product_full(self):
        result = self.crawler.extract_product("https://item.jd.com/123456.html", _PRODUCT_HTML)
        assert result["name"] == "测试商品名称 2024款"
        assert result["price"] == 299.0
        assert result["platform_product_id"] == "123456"
        assert result["platform"] == "jd"
        assert "img.example.com" in result["image"]
        assert result["shop"] == "测试旗舰店"

    def test_extract_product_minimal_html(self):
        html = "<html><body><div class='sku-name'>单品</div></body></html>"
        result = self.crawler.extract_product("https://item.jd.com/789.html", html)
        assert result["name"] == "单品"
        assert result["platform_product_id"] == "789"

    def test_extract_product_no_name_raises(self):
        with pytest.raises(ExtractionError):
            self.crawler.extract_product("https://item.jd.com/1.html", "<html></html>")

    def test_extract_product_no_price(self):
        html = "<html><body><div class='sku-name'>无价格商品</div></body></html>"
        result = self.crawler.extract_product("https://item.jd.com/456.html", html)
        assert result["price"] is None
        assert result["name"] == "无价格商品"

    def test_extract_product_no_product_id(self):
        """When URL has no product ID, field is empty string."""
        html = "<html><body><div class='sku-name'>无名商品</div></body></html>"
        result = self.crawler.extract_product("https://example.com/no-id", html)
        assert result["platform_product_id"] == ""


class TestJDCrawlerReviews:
    def setup_method(self):
        self.crawler = JDCrawler()

    def test_extract_reviews_full(self):
        reviews = self.crawler.extract_reviews("https://item.jd.com/123.html", _REVIEW_JSONP, page=1)
        # 4 comments, 1 empty content -> 3 valid
        assert len(reviews) == 3
        assert reviews[0]["content"] == "好评，质量很好"
        assert reviews[0]["rating"] == 5
        assert reviews[0]["author_name"] == "用户A"
        assert reviews[0]["platform"] == "jd"

    def test_extract_reviews_empty_page(self):
        reviews = self.crawler.extract_reviews("https://item.jd.com/123.html", _EMPTY_REVIEW_JSONP, page=5)
        assert reviews == []

    def test_extract_reviews_invalid_json(self):
        with pytest.raises(ExtractionError):
            self.crawler.extract_reviews("https://item.jd.com/123.html", "not-json{", page=1)

    def test_extract_reviews_rating_conversion(self):
        """Verify string/invalid ratings default to 0."""
        jsonp = """cb({"comments": [
            {"content": "好评", "score": "5", "nickname": "A"},
            {"content": "中评", "score": null, "nickname": "B"},
            {"content": "差评", "score": "abc", "nickname": "C"}
        ]})"""
        reviews = self.crawler.extract_reviews("https://item.jd.com/123.html", jsonp, page=1)
        assert reviews[0]["rating"] == 5
        assert reviews[1]["rating"] == 0
        assert reviews[2]["rating"] == 0

    def test_get_review_url_format(self):
        url = self.crawler.get_review_url("https://item.jd.com/123456.html", page=2)
        assert "club.jd.com" in url
        assert "productId=123456" in url
        assert "page=2" in url
        assert "pageSize=10" in url

    def test_get_review_url_no_product_id(self):
        with pytest.raises(ExtractionError):
            self.crawler.get_review_url("https://example.com/no-id", page=1)

    def test_estimate_total_pages(self):
        pages = self.crawler._estimate_total_pages(_REVIEW_JSONP)
        assert pages == 50

    def test_estimate_total_pages_empty(self):
        pages = self.crawler._estimate_total_pages(_EMPTY_REVIEW_JSONP)
        assert pages == 0


class TestJDCrawlerIntegration:
    def test_crawl_all_product_only_no_reviews(self):
        """Verify crawl_all works when no review URL pattern is cached."""
        crawler = JDCrawler()

        # Mock _fetch_with_retry to return product HTML first, then review JSONP
        calls = [0]

        def mock_fetch(url):
            calls[0] += 1
            if calls[0] == 1:
                return _PRODUCT_HTML
            return _REVIEW_JSONP

        crawler._fetch_with_retry = mock_fetch
        result = crawler.crawl_all("https://item.jd.com/123456.html", page_limit=2)
        assert result.product is not None
        assert result.product["name"] == "测试商品名称 2024款"
        assert len(result.reviews) > 0
        assert result.total_pages == 50
