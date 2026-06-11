"""Tests for Taobao and PDD crawler adapters.

Uses mock HTML/JSON fixtures and unit-test patterns (no real HTTP).
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.crawler.base import ExtractionError, CrawlerResult
from app.crawler.adapters.taobao import TaobaoCrawler
from app.crawler.adapters.pdd import PDDCrawler
from app.crawler.adapters import get_crawler, register_crawler


# ===================================================================
# Taobao HTML fixture (item.taobao.com)
# ===================================================================
_TAOBAO_PRODUCT_HTML = """
<html>
<head><title>2024新款国潮卫衣-淘宝网</title></head>
<body>
  <div class="tb-title">2024新款国潮卫衣 春秋季百搭</div>
  <span class="tm-price">¥168.00</span>
  <div class="tb-shop-name"><a>潮流服饰旗舰店</a></div>
  <div class="tb-pic"><img src="//img.taobao.com/test.jpg" /></div>
</body>
</html>
"""

# Tmall HTML fixture
_TMALL_PRODUCT_HTML = """
<html>
<head><title>官方正品运动鞋-天猫</title></head>
<body>
  <div class="main-title">官方正品运动鞋 透气跑步鞋</div>
  <span class="tm-price">¥399.00</span>
  <div class="shop-name"><a>运动户外旗舰店</a></div>
  <div class="pic"><img data-src="//img.tmall.com/shoe.jpg" /></div>
</body>
</html>
"""

# Taobao review JSON fixture
_TAOBAO_REVIEW_JSON = json.dumps({
    "comments": [
        {"rateContent": "质量很好，推荐购买", "rateDate": "2024-06-01", "rateScore": 5,
         "displayUserInfo": {"displayUserNick": "用户A"}, "id": 1001},
        {"rateContent": "一般般吧", "rateDate": "2024-05-28", "rateScore": 3,
         "displayUserInfo": {"displayUserNick": "用户B"}, "id": 1002},
        {"rateContent": "颜色不对，差评", "rateDate": "2024-05-25", "rateScore": 1,
         "displayUserInfo": {"displayUserNick": "用户C"}, "id": 1003},
    ],
    "totalCount": 50,
})

# Tmall review JSON fixture
_TMALL_REVIEW_JSON = json.dumps({
    "rateDetail": {
        "rateList": [
            {"rateContent": "鞋子很舒服", "rateDate": "2024-06-10", "rateScore": 5,
             "displayUserInfo": {"displayUserNick": "用户X"}, "id": 2001},
            {"rateContent": "尺码偏小", "rateDate": "2024-06-08", "rateScore": 3,
             "displayUserInfo": {"displayUserNick": "用户Y"}, "id": 2002},
        ],
        "rateCount": 30,
    }
})


# ===================================================================
# PDD HTML / JSON fixtures
# ===================================================================
_PDD_PRODUCT_HTML = """
<html>
<head><title>无线蓝牙耳机-拼多多</title></head>
<body>
  <div class="goods-title">无线蓝牙耳机 5.3 超长续航</div>
  <div class="price">¥25.90</div>
  <div class="goods-img"><img data-src="//img.pdd.com/earphone.jpg" /></div>
  <script>
    window.__INITIAL_STATE__ = {"goods": {"goodsName": "无线蓝牙耳机 5.3", "price": 25.9, "thumbUrl": "//img.pdd.com/earphone.jpg", "mallName": "数码优选"}};
  </script>
</body>
</html>
"""

_PDD_REVIEW_JSON = json.dumps({
    "data": {
        "reviews": [
            {"content": "音质效果很好", "rateTime": 1718000000000, "score": 5,
             "nickname": "买家A", "id": 3001, "skuInfo": "黑色"},
            {"content": "续航不错", "rateTime": 1717900000000, "score": 4,
             "nickname": "买家B", "id": 3002, "skuInfo": "白色"},
            {"content": "有点延迟", "rateTime": 1717800000000, "score": 2,
             "nickname": "买家C", "id": 3003, "skuInfo": "黑色"},
        ],
        "total": 100,
    }
})


# ===================================================================
# Taobao Crawler Tests
# ===================================================================

class TestTaobaoCrawler:
    """Unit tests for TaobaoCrawler product & review extraction."""

    TAOBAO_URL = "https://item.taobao.com/item.htm?id=123456789"
    TMALL_URL = "https://detail.tmall.com/item.htm?id=987654321"

    def test_extract_product_taobao(self):
        crawler = TaobaoCrawler()
        result = crawler.extract_product(self.TAOBAO_URL, _TAOBAO_PRODUCT_HTML)
        assert result["name"] == "2024新款国潮卫衣 春秋季百搭"
        assert result["price"] == 168.0
        assert result["platform_product_id"] == "123456789"
        assert result["platform"] == "taobao"
        assert "test.jpg" in result["image"]
        assert result["shop"] == "潮流服饰旗舰店"

    def test_extract_product_tmall(self):
        """Tmall URL should also be parsed correctly by TaobaoCrawler."""
        crawler = TaobaoCrawler()
        result = crawler.extract_product(self.TMALL_URL, _TMALL_PRODUCT_HTML)
        assert "运动鞋" in result["name"]
        assert result["price"] == 399.0
        assert result["platform_product_id"] == "987654321"
        assert "shoe.jpg" in result["image"]

    def test_extract_product_empty_name_raises(self):
        crawler = TaobaoCrawler()
        with pytest.raises(ExtractionError, match="Could not extract product name"):
            crawler.extract_product(self.TAOBAO_URL, "<html></html>")

    def test_extract_reviews_taobao(self):
        crawler = TaobaoCrawler()
        reviews = crawler.extract_reviews(self.TAOBAO_URL, _TAOBAO_REVIEW_JSON)
        assert len(reviews) == 3
        assert reviews[0]["content"] == "质量很好，推荐购买"
        assert reviews[0]["rating"] == 5
        assert reviews[0]["author_name"] == "用户A"
        assert reviews[0]["purchase_time"] == "2024-06-01"
        assert reviews[0]["platform"] == "taobao"

    def test_extract_reviews_tmall(self):
        crawler = TaobaoCrawler()
        reviews = crawler.extract_reviews(self.TMALL_URL, _TMALL_REVIEW_JSON)
        assert len(reviews) == 2
        assert reviews[0]["content"] == "鞋子很舒服"
        assert reviews[0]["rating"] == 5
        assert reviews[0]["author_name"] == "用户X"

    def test_extract_reviews_empty(self):
        crawler = TaobaoCrawler()
        reviews = crawler.extract_reviews(self.TAOBAO_URL, "{}")
        assert reviews == []

    def test_extract_reviews_bad_json_raises(self):
        crawler = TaobaoCrawler()
        with pytest.raises(ExtractionError):
            crawler.extract_reviews(self.TAOBAO_URL, "not-json")

    def test_get_review_url_taobao(self):
        crawler = TaobaoCrawler()
        crawler._product_id_cache[self.TAOBAO_URL] = "123456789"
        url = crawler.get_review_url(self.TAOBAO_URL, page=2)
        assert "rate.taobao.com" in url
        assert "auctionNumId=123456789" in url
        assert "currentPage=2" in url

    def test_get_review_url_tmall(self):
        crawler = TaobaoCrawler()
        crawler._product_id_cache[self.TMALL_URL] = "987654321"
        crawler._is_tmall_cache[self.TMALL_URL] = True
        url = crawler.get_review_url(self.TMALL_URL, page=1)
        assert "rate.tmall.com" in url
        assert "itemId=987654321" in url

    def test_get_review_url_no_id_raises(self):
        crawler = TaobaoCrawler()
        with pytest.raises(ExtractionError):
            crawler.get_review_url("https://example.com/no-id", page=1)

    def test_estimate_total_pages_taobao(self):
        crawler = TaobaoCrawler()
        pages = crawler._estimate_total_pages(_TAOBAO_REVIEW_JSON)
        assert pages == 3  # 50 comments, 20 per page → ceil(50/20) = 3

    def test_estimate_total_pages_tmall(self):
        crawler = TaobaoCrawler()
        pages = crawler._estimate_total_pages(_TMALL_REVIEW_JSON)
        assert pages == 2  # 30 comments, 20 per page → ceil(30/20) = 2

    def test_crawl_product_success(self):
        crawler = TaobaoCrawler()
        crawler._fetch_with_retry = MagicMock(return_value=_TAOBAO_PRODUCT_HTML)
        result = crawler.crawl_product(self.TAOBAO_URL)
        assert result.product is not None
        assert result.product["name"] == "2024新款国潮卫衣 春秋季百搭"
        assert result.error is None

    def test_crawl_product_fetch_fail(self):
        crawler = TaobaoCrawler()
        crawler._fetch_with_retry = MagicMock(return_value=None)
        result = crawler.crawl_product(self.TAOBAO_URL)
        assert result.product is None
        assert result.error is not None


# ===================================================================
# PDD Crawler Tests
# ===================================================================

class TestPDDCrawler:
    """Unit tests for PDDCrawler product & review extraction."""

    PDD_URL = "https://mobile.yangkeduo.com/goods.html?goods_id=555666777"

    def test_extract_product(self):
        crawler = PDDCrawler()
        result = crawler.extract_product(self.PDD_URL, _PDD_PRODUCT_HTML)
        assert "蓝牙耳机" in result["name"]
        assert result["price"] == 25.9
        assert result["platform_product_id"] == "555666777"
        assert result["platform"] == "pdd"
        assert "earphone.jpg" in result["image"]
        assert result["shop"] == "数码优选"

    def test_extract_product_empty_name_raises(self):
        crawler = PDDCrawler()
        with pytest.raises(ExtractionError, match="Could not extract product name"):
            crawler.extract_product(self.PDD_URL, "<html></html>")

    def test_extract_reviews(self):
        crawler = PDDCrawler()
        reviews = crawler.extract_reviews(self.PDD_URL, _PDD_REVIEW_JSON)
        assert len(reviews) == 3
        assert reviews[0]["content"] == "音质效果很好"
        assert reviews[0]["rating"] == 5
        assert reviews[0]["author_name"] == "买家A"
        assert reviews[0]["platform"] == "pdd"
        assert "黑色" in reviews[0]["product_color"]

    def test_extract_reviews_empty(self):
        crawler = PDDCrawler()
        reviews = crawler.extract_reviews(self.PDD_URL, "{}")
        assert reviews == []

    def test_extract_reviews_bad_json_raises(self):
        crawler = PDDCrawler()
        with pytest.raises(ExtractionError):
            crawler.extract_reviews(self.PDD_URL, "not-json")

    def test_get_review_url(self):
        crawler = PDDCrawler()
        crawler._product_id_cache[self.PDD_URL] = "555666777"
        url = crawler.get_review_url(self.PDD_URL, page=3)
        assert "mobile.yangkeduo.com" in url
        assert "goods_id=555666777" in url
        assert "page=3" in url
        assert "size=10" in url

    def test_get_review_url_no_id_raises(self):
        crawler = PDDCrawler()
        with pytest.raises(ExtractionError):
            crawler.get_review_url("https://example.com/no-id", page=1)

    def test_estimate_total_pages(self):
        crawler = PDDCrawler()
        pages = crawler._estimate_total_pages(_PDD_REVIEW_JSON)
        assert pages == 10  # 100 reviews, 10 per page

    def test_extract_embedded_json(self):
        crawler = PDDCrawler()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(_PDD_PRODUCT_HTML, "html.parser")
        data = crawler._extract_embedded_json(soup)
        assert data is not None
        assert data.get("goodsName") == "无线蓝牙耳机 5.3"

    def test_crawl_product_success(self):
        crawler = PDDCrawler()
        crawler._fetch_with_retry = MagicMock(return_value=_PDD_PRODUCT_HTML)
        result = crawler.crawl_product(self.PDD_URL)
        assert result.product is not None
        assert result.error is None

    def test_crawl_product_fetch_fail(self):
        crawler = PDDCrawler()
        crawler._fetch_with_retry = MagicMock(return_value=None)
        result = crawler.crawl_product(self.PDD_URL)
        assert result.product is None
        assert result.error is not None


# ===================================================================
# Crawler Registry Tests
# ===================================================================

class TestCrawlerRegistry:
    """Tests for the get_crawler factory function."""

    def test_get_jd_crawler(self):
        crawler = get_crawler("jd")
        assert crawler.platform == "jd"

    def test_get_taobao_crawler(self):
        crawler = get_crawler("taobao")
        assert crawler.platform == "taobao"

    def test_get_pdd_crawler(self):
        crawler = get_crawler("pdd")
        assert crawler.platform == "pdd"

    def test_get_crawler_with_kwargs(self):
        crawler = get_crawler("taobao", min_delay=3.0, max_delay=6.0)
        assert crawler.anti_bot.min_delay == 3.0
        assert crawler.anti_bot.max_delay == 6.0

    def test_get_crawler_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            get_crawler("amazon")

    def test_register_crawler(self):
        class FakeCrawler:
            platform = "fake"
        register_crawler("fake", FakeCrawler)
        instance = get_crawler("fake")
        assert instance.platform == "fake"
