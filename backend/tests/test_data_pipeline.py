"""Tests for the data pipeline: text_cleaner, DataPipeline service, and integration."""
import pytest
import hashlib

from app.utils.text_cleaner import clean_text, normalize_rating, is_valid_review, detect_language, content_hash
from app.services.data_pipeline import DataPipeline, ProcessedReview, DataPipelineResult
from app.models.comment import Comment
from app.models.product import Product


# ── text_cleaner tests ─────────────────────────────────────────────────

class TestCleanText:
    def test_strip_urls(self):
        assert clean_text("看看这个 https://item.jd.com/123.html 怎么样") == "看看这个怎么样"

    def test_strip_html(self):
        assert clean_text("<p>质量很好</p>") == "质量很好"

    def test_collapse_whitespace(self):
        assert clean_text("质量  很好  推荐") == "质量很好推荐"

    def test_truncate_repeats(self):
        assert clean_text("好好好好好好") == "好好好好"

    def test_replace_ellipsis(self):
        assert clean_text("继续…") == "继续..."

    def test_empty_input(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_url_and_html_combined(self):
        result = clean_text('<a href="http://example.com">好评</a> 真的很好用')
        assert "好评" in result
        assert "http" not in result
        assert "<a" not in result


class TestNormalizeRating:
    def test_valid_integer(self):
        assert normalize_rating(5) == 5
        assert normalize_rating(1) == 1

    def test_valid_float_rounds(self):
        assert normalize_rating(4.7) == 5
        assert normalize_rating(2.3) == 2

    def test_clamps_out_of_range(self):
        assert normalize_rating(0) == 1
        assert normalize_rating(6) == 5
        assert normalize_rating(-1) == 1

    def test_none_or_invalid_defaults_to_3(self):
        assert normalize_rating(None) == 3
        assert normalize_rating("abc") == 3
        assert normalize_rating("") == 3

    def test_string_number_converts(self):
        assert normalize_rating("4.5") == 5
        assert normalize_rating("3") == 3


class TestIsValidReview:
    def test_valid_chinese_review(self):
        assert is_valid_review("质量很好推荐购买") is True

    def test_too_short(self):
        assert is_valid_review("好") is False

    def test_empty(self):
        assert is_valid_review("") is False

    def test_punctuation_only(self):
        assert is_valid_review("!!!。。。") is False

    def test_over_max_length(self):
        long_text = "a" * 10001
        assert is_valid_review(long_text, max_length=10000) is False

    def test_custom_min_length(self):
        assert is_valid_review("abc", min_length=5) is False
        assert is_valid_review("abcde", min_length=5) is True


class TestDetectLanguage:
    def test_chinese_dominant(self):
        assert detect_language("质量很好推荐购买") == "zh"

    def test_non_chinese(self):
        assert detect_language("This is a great product") == "other"

    def test_mixed_but_above_threshold(self):
        """30%+ Chinese chars → zh."""
        text = "质量good非常好nice"
        assert detect_language(text) == "zh"

    def test_empty(self):
        assert detect_language("") == "other"


class TestContentHash:
    def test_consistency(self):
        text = "质量很好推荐购买"
        assert content_hash(text) == content_hash(text)

    def test_different_inputs_different_hashes(self):
        assert content_hash("质量很好") != content_hash("质量很差")

    def test_cleans_before_hashing(self):
        """URLs should be stripped before hashing."""
        h1 = content_hash("看看这个 https://item.jd.com/123.html 怎么样")
        h2 = content_hash("看看这个怎么样")
        assert h1 == h2

    def test_sha256_length(self):
        h = content_hash("测试评论")
        assert len(h) == 64
        int(h, 16)  # should be valid hex


# ── DataPipeline tests ─────────────────────────────────────────────────

class TestDataPipelineProcessReview:
    def test_valid_review(self):
        review = {"content": "质量很好推荐购买", "rating": 5, "author_name": "用户A", "platform": "jd"}
        pr = DataPipeline.process_review(review, product_id=1)
        assert pr is not None
        assert pr.content == "质量很好推荐购买"
        assert pr.rating == 5
        assert pr.author_name == "用户A"
        assert pr.platform == "jd"
        assert pr.source == "import"  # default
        assert len(pr.content_hash) == 64

    def test_empty_content_returns_none(self):
        review = {"content": ""}
        assert DataPipeline.process_review(review, product_id=1) is None

    def test_too_short_content_returns_none(self):
        review = {"content": "好"}
        assert DataPipeline.process_review(review, product_id=1) is None

    def test_non_chinese_short_review_filtered(self):
        review = {"content": "hello world"}
        assert DataPipeline.process_review(review, product_id=1) is None

    def test_rating_normalized(self):
        assert DataPipeline.process_review({"content": "质量很好推荐购买", "rating": 0}, 1).rating == 1
        assert DataPipeline.process_review({"content": "质量很好推荐购买", "rating": 6}, 1).rating == 5
        assert DataPipeline.process_review({"content": "质量很好推荐购买", "rating": None}, 1).rating == 3

    def test_chinese_column_names(self):
        review = {"评论内容": "质量很好推荐购买", "评分": "4.5", "用户名": "张三", "平台": "京东"}
        pr = DataPipeline.process_review(review, product_id=1)
        assert pr is not None
        assert pr.content == "质量很好推荐购买"
        assert pr.rating == 5
        assert pr.author_name == "张三"
        assert pr.platform == "京东"

    def test_purchase_time_string_conversion(self):
        review = {"content": "质量很好推荐购买", "purchase_time": "2024-01-15"}
        pr = DataPipeline.process_review(review, product_id=1)
        import datetime
        assert pr.purchase_time == datetime.date(2024, 1, 15)

    def test_purchase_time_invalid_string(self):
        review = {"content": "质量很好推荐购买", "purchase_time": "not-a-date"}
        pr = DataPipeline.process_review(review, product_id=1)
        assert pr.purchase_time is None

    def test_source_preserved(self):
        review = {"content": "质量很好推荐购买", "source": "crawl"}
        pr = DataPipeline.process_review(review, product_id=1)
        assert pr.source == "crawl"

    def test_clean_text_before_hash(self):
        """Text with URL and without URL should produce same hash."""
        pr1 = DataPipeline.process_review({"content": "看看 https://jd.com 怎么样"}, 1)
        pr2 = DataPipeline.process_review({"content": "看看怎么样"}, 1)
        assert pr1.content_hash == pr2.content_hash


class TestDataPipelineFilterExistingHashes:
    def test_all_new(self, app, db, sample_product):
        with app.app_context():
            hashes = {"aaa" + "0" * 61, "bbb" + "0" * 61}
            new = DataPipeline.filter_existing_hashes(db.session, sample_product.id, hashes)
            assert new == hashes

    def test_some_exist(self, app, db, sample_product):
        with app.app_context():
            existing_hash = content_hash("已有评论")
            db.session.add(Comment(
                product_id=sample_product.id,
                content="已有评论",
                content_hash=existing_hash,
                rating=5,
            ))
            db.session.commit()

            input_hashes = {existing_hash, "new" + "0" * 61}
            new = DataPipeline.filter_existing_hashes(db.session, sample_product.id, input_hashes)
            assert existing_hash not in new
            assert "new" + "0" * 61 in new

    def test_empty_set(self, app, db, sample_product):
        with app.app_context():
            assert DataPipeline.filter_existing_hashes(db.session, sample_product.id, set()) == set()

    def test_scoped_by_product(self, app, db):
        with app.app_context():
            p1 = Product(name="商品A", platform="jd", user_id=1)
            p2 = Product(name="商品B", platform="jd", user_id=1)
            db.session.add_all([p1, p2])
            db.session.flush()

            h = content_hash("相同内容")
            db.session.add(Comment(product_id=p1.id, content="相同内容", content_hash=h, rating=3))
            db.session.commit()

            # Same hash should be "new" for p2 since it's scoped per product
            new = DataPipeline.filter_existing_hashes(db.session, p2.id, {h})
            assert h in new


class TestDataPipelineProcessBatch:
    def test_batch_with_dedup(self):
        reviews = [
            {"content": "质量很好推荐购买", "rating": 5},
            {"content": "质量很好推荐购买", "rating": 5},  # duplicate
            {"content": "质量还算可以", "rating": 3},
        ]
        result, processed = DataPipeline.process_batch(reviews, product_id=1)
        assert result.total == 3
        assert result.new == 2
        assert result.skipped_dup == 1
        assert result.filtered == 0
        assert len(processed) == 2

    def test_batch_filters_invalid(self):
        reviews = [
            {"content": "质量很好推荐购买", "rating": 5},
            {"content": ""},  # filtered
            {"content": "好"},  # too short
        ]
        result, processed = DataPipeline.process_batch(reviews, product_id=1)
        assert result.total == 3
        assert result.new == 1
        assert result.filtered == 2
        assert len(processed) == 1

    def test_batch_all_invalid(self):
        reviews = [
            {"content": ""},
            {"content": "好"},
            {"content": "a"},
        ]
        result, processed = DataPipeline.process_batch(reviews, product_id=1)
        assert result.new == 0
        assert result.filtered == 3
        assert len(processed) == 0

    def test_batch_with_db_session(self, app, db, sample_product):
        with app.app_context():
            # Pre-insert a comment so it exists in DB
            existing_pr = DataPipeline.process_review({"content": "这条评论已存在", "rating": 5}, sample_product.id)
            db.session.add(Comment(
                product_id=sample_product.id,
                content=existing_pr.content,
                content_hash=existing_pr.content_hash,
                rating=5,
            ))
            db.session.commit()

            reviews = [
                {"content": "这条评论已存在", "rating": 5},  # exists in DB
                {"content": "新评论一条记录", "rating": 4},
            ]
            result, processed = DataPipeline.process_batch(
                reviews, sample_product.id, session=db.session,
            )
            assert result.new == 1
            assert result.skipped_dup == 1  # DB-level dedup
            assert len(processed) == 1
            assert processed[0].content == "新评论一条记录"


# ── Integration tests ─────────────────────────────────────────────────

class TestDataPipelineIntegration:
    def test_comment_creation_with_hash(self, app, db, sample_product):
        """Verify that comments created via the pipeline store content_hash."""
        from app.services.comment_service import import_comments_from_csv
        import io

        csv_content = "content,rating,author_name\n质量很好推荐购买,5,用户A\n"
        file_storage = io.BytesIO(csv_content.encode("utf-8"))

        with app.app_context():
            result = import_comments_from_csv(file_storage, sample_product.id)

            assert result.total == 1
            assert result.imported == 1

            comment = Comment.query.filter_by(product_id=sample_product.id).first()
            assert comment is not None
            assert comment.content_hash == content_hash("质量很好推荐购买")
            assert len(comment.content_hash) == 64

    def test_csv_dedup_by_hash(self, app, db, sample_product):
        """Verify CSV import dedup works via content_hash."""
        from app.services.comment_service import import_comments_from_csv
        import io

        csv_content = "content,rating,author_name\n质量很好推荐购买,5,用户A\n"
        file_storage = io.BytesIO(csv_content.encode("utf-8"))

        with app.app_context():
            # First import
            r1 = import_comments_from_csv(file_storage, sample_product.id)
            assert r1.imported == 1

            # Second import — same CSV content
            file_storage.seek(0)
            r2 = import_comments_from_csv(file_storage, sample_product.id)

            assert r2.total == 1
            assert r2.imported == 0
            assert r2.skipped == 1

    def test_crawl_task_with_pipeline(self, app, db):
        """Verify crawl_tasks flow works with DataPipeline (content_hash)."""
        from app.tasks.crawl_tasks import run_crawl
        from app.models.crawl_task import CrawlTask
        from unittest.mock import patch

        with app.app_context():
            task = CrawlTask(
                name="测试爬虫",
                platform="jd",
                url="https://item.jd.com/123456.html",
                page_limit=2,
                status="pending",
                user_id=1,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        with app.app_context():
            with patch("app.tasks.crawl_tasks.get_crawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult

                instance.crawl_all.return_value = CrawlerResult(
                    product={"name": "测试商品", "platform_product_id": "123456", "platform": "jd"},
                    reviews=[
                        {"content": "非常好用推荐购买", "rating": 5, "author_name": "用户A",
                         "platform": "jd", "purchase_time": "2024-01-15"},
                        {"content": "质量还算可以吧", "rating": 3, "author_name": "用户B",
                         "platform": "jd", "purchase_time": "2024-01-14"},
                    ],
                    total_pages=1, current_page=1, items_found=2,
                )

                run_crawl(task_id)

            task = db.session.get(CrawlTask, task_id)
            assert task.status == "completed"
            assert task.items_new == 2

            comments = Comment.query.all()
            assert len(comments) == 2
            for c in comments:
                assert c.content_hash is not None
                assert len(c.content_hash) == 64

    def test_crawl_dedup_re_crawl(self, app, db):
        """Verify re-crawling same product dedup via content_hash."""
        from app.tasks.crawl_tasks import run_crawl
        from app.models.crawl_task import CrawlTask
        from unittest.mock import patch

        with app.app_context():
            task1 = CrawlTask(
                name="第一次爬虫", platform="jd",
                url="https://item.jd.com/123456.html",
                page_limit=2, status="pending", user_id=1,
            )
            db.session.add(task1)
            db.session.commit()

            with patch("app.tasks.crawl_tasks.get_crawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    product={"name": "测试商品", "platform_product_id": "123456", "platform": "jd"},
                    reviews=[{"content": "唯一的一条评论", "rating": 5, "author_name": "用户X", "platform": "jd"}],
                    total_pages=1, current_page=1, items_found=1,
                )
                run_crawl(task1.id)

            assert Comment.query.count() == 1

            # Re-crawl with same data
            with patch("app.tasks.crawl_tasks.get_crawler") as MockCrawler:
                instance = MockCrawler.return_value
                from app.crawler.base import CrawlerResult
                instance.crawl_all.return_value = CrawlerResult(
                    product={"name": "测试商品", "platform_product_id": "123456", "platform": "jd"},
                    reviews=[{"content": "唯一的一条评论", "rating": 5, "author_name": "用户X", "platform": "jd"}],
                    total_pages=1, current_page=1, items_found=1,
                )
                run_crawl(task1.id)

            # Should still be 1 comment (dedup by hash)
            assert Comment.query.count() == 1

    def test_analysis_text_cleaning(self, app, db):
        """Verify that analysis_tasks cleans text before analyzing."""
        from app.tasks.analysis_tasks import run_analysis
        from app.models.analysis_task import AnalysisTask
        from unittest.mock import patch

        with app.app_context():
            product = Product(name="测试", platform="jd", user_id=1)
            db.session.add(product)
            db.session.flush()

            comment = Comment(
                product_id=product.id,
                content='质量很好 <a href="http://spam.com">链接</a> 推荐购买',
                rating=5,
            )
            db.session.add(comment)
            db.session.commit()

            task = AnalysisTask(
                name="测试分析",
                user_id=1,
                status="pending",
                total_count=1,
            )
            db.session.add(task)
            db.session.commit()

            with patch("app.tasks.analysis_tasks.SentimentService") as MockService:
                instance = MockService.return_value
                instance.analyze.return_value = {
                    "sentiment": "positive",
                    "sentiment_score": 0.95,
                    "aspects": {"quality": 0.9},
                    "keywords": ["质量"],
                    "summary": "好评",
                    "fake_score": 0.1,
                }

                run_analysis(task.id, [comment.id])

            # Verify that cleaned text (no HTML/URL) was passed to the model
            instance.analyze.assert_called_once()
            call_arg = instance.analyze.call_args[0][0]
            assert "http" not in call_arg
            assert "<a" not in call_arg
            assert "质量很好" in call_arg
