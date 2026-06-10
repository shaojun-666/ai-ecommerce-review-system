"""End-to-end tests for the crawl pipeline.

Uses mock HTTP server and SQLite in-memory database to test
the full crawl → filter → store flow.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models.crawl_task import CrawlTask
from app.models.product import Product
from app.models.comment import Comment
from app.tasks.crawl_tasks import run_crawl

# JD product HTML fixture
_PRODUCT_HTML = """
<html>
<head><title>测试商品【京东】</title></head>
<body>
  <div class="sku-name">测试商品 2024款</div>
  <span class="p-price">¥199.00</span>
</body>
</html>
"""

# Review JSONP (3 valid reviews)
_REVIEW_JSONP = """fetchJSON_comment98vv123({
  "comments": [
    {"id": 1, "content": "非常好用推荐购买", "creationTime": "2024-01-15", "score": 5, "nickname": "用户A"},
    {"id": 2, "content": "质量一般吧", "creationTime": "2024-01-14", "score": 3, "nickname": "用户B"},
    {"id": 3, "content": "差评不推荐", "creationTime": "2024-01-13", "score": 1, "nickname": "用户C"}
  ],
  "productCommentSummary": {"maxPage": 5}
})"""


class TestCrawlTaskE2E:
    @pytest.fixture(autouse=True)
    def setup(self, app, db):
        """Create a crawl task for testing."""
        self.app = app
        self.db = db
        self.task = CrawlTask(
            name="测试爬虫",
            platform="jd",
            url="https://item.jd.com/123456.html",
            page_limit=2,
            status="pending",
            user_id=1,
        )
        db.session.add(self.task)
        db.session.commit()
        self.task_id = self.task.id

    def _mock_fetch(self, url):
        """Simulate fetch returning product HTML and review JSONP."""
        if "club.jd.com" in url:
            return _REVIEW_JSONP
        return _PRODUCT_HTML

    def test_run_crawl_success(self, app):
        """Full crawl flow: task → crawl → product upsert → comments insert."""
        with app.app_context():
            with patch("app.tasks.crawl_tasks.JDCrawler") as MockCrawler:
                # Configure the mock crawler
                instance = MockCrawler.return_value

                # Mock crawl_all result
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    product={
                        "name": "测试商品 2024款",
                        "platform_product_id": "123456",
                        "price": 199.0,
                        "platform": "jd",
                    },
                    reviews=[
                        {"content": "非常好用推荐购买", "rating": 5, "author_name": "用户A", "platform": "jd", "purchase_time": "2024-01-15"},
                        {"content": "质量一般吧", "rating": 3, "author_name": "用户B", "platform": "jd", "purchase_time": "2024-01-14"},
                        {"content": "差评不推荐", "rating": 1, "author_name": "用户C", "platform": "jd", "purchase_time": "2024-01-13"},
                    ],
                    total_pages=5,
                    current_page=2,
                    items_found=3,
                )

                run_crawl(self.task_id)

        # Verify results
        with app.app_context():
            task = db.session.get(CrawlTask, self.task_id)
            assert task.status == "completed"
            assert task.items_found == 3
            assert task.items_new == 3

            # Product should be created
            product = Product.query.filter_by(platform="jd").first()
            assert product is not None
            assert "测试商品" in product.name

            # Comments should be inserted
            comments = Comment.query.filter_by(product_id=product.id).all()
            assert len(comments) == 3

    def test_run_crawl_dedup(self, app):
        """Verify duplicate comments are not inserted on re-crawl."""
        with app.app_context():
            # First crawl
            with patch("app.tasks.crawl_tasks.JDCrawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    product={"name": "测试商品", "platform_product_id": "123456", "platform": "jd"},
                    reviews=[{"content": "唯一的一条评论", "rating": 5, "author_name": "用户X", "platform": "jd", "purchase_time": "2024-01-01"}],
                    total_pages=1, current_page=1, items_found=1,
                )
                run_crawl(self.task_id)

            # Second crawl with same data
            task2 = CrawlTask(
                name="第二次爬虫",
                platform="jd",
                url="https://item.jd.com/123456.html",
                page_limit=2,
                status="pending",
                user_id=1,
            )
            db.session.add(task2)
            db.session.flush()

            with patch("app.tasks.crawl_tasks.JDCrawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    product={"name": "测试商品", "platform_product_id": "123456", "platform": "jd"},
                    reviews=[{"content": "唯一的一条评论", "rating": 5, "author_name": "用户X", "platform": "jd", "purchase_time": "2024-01-01"}],
                    total_pages=1, current_page=1, items_found=1,
                )
                run_crawl(task2.id)

            # Should still only be 1 comment
            product = Product.query.filter_by(platform="jd").first()
            comments = Comment.query.filter_by(product_id=product.id).all()
            assert len(comments) == 1

    def test_run_crawl_blocked(self, app):
        """Verify blocked crawl is marked as failed."""
        with app.app_context():
            with patch("app.tasks.crawl_tasks.JDCrawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    blocked=True,
                    error="Block signature detected: captcha",
                )
                run_crawl(self.task_id)

            task = db.session.get(CrawlTask, self.task_id)
            assert task.status == "failed"
            assert "blocked" in task.error_message.lower()

    def test_run_crawl_product_not_found(self, app):
        """Verify task fails gracefully when crawl returns no product."""
        with app.app_context():
            with patch("app.tasks.crawl_tasks.JDCrawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    error="Failed to extract product",
                )
                run_crawl(self.task_id)

            task = db.session.get(CrawlTask, self.task_id)
            assert task.status == "failed"
