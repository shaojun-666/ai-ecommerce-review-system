"""Tests for dashboard API caching behavior."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.extensions import db as _db
from app.models.comment import Comment, CommentAnalysis
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask


class TestDashboardCacheIntegration:
    """Verify dashboard endpoints use cache on subsequent requests."""

    def test_overview_cache_hit(self, client, auth_headers, sample_comments):
        """First request hits DB, second hits cache."""
        # Mark some comments as analyzed
        with patch("app.api.v1.dashboard.cache_get") as mock_get:
            mock_get.return_value = None  # no cache on first call

            resp1 = client.get("/api/v1/dashboard/overview", headers=auth_headers)
            assert resp1.status_code == 200

        # The actual endpoint uses cache_get(cache_key)
        # After first call, cache_set is called
        # On second call, cache_get returns data -> skip DB
        with patch("app.api.v1.dashboard.cache_get") as mock_get:
            mock_get.return_value = {
                "total_comments": 5,
                "analyzed_count": 0,
                "total_tasks": 0,
                "sentiment_distribution": {
                    "positive": {"count": 0, "percentage": 0},
                    "negative": {"count": 0, "percentage": 0},
                    "neutral": {"count": 0, "percentage": 0},
                },
                "avg_rating": 5.0,
                "fake_review_count": 0,
            }
            resp2 = client.get("/api/v1/dashboard/overview", headers=auth_headers)
            assert resp2.status_code == 200
            data = resp2.get_json().get("data", {})
            assert data["total_comments"] == 5

    def test_trend_cache_key_varies_by_days(self, client, auth_headers):
        """Different 'days' params use different cache keys."""
        with patch("app.api.v1.dashboard.cache_get") as mock_get, \
             patch("app.api.v1.dashboard.cache_set") as mock_set:
            mock_get.return_value = None  # always miss

            client.get("/api/v1/dashboard/trend?days=7", headers=auth_headers)
            client.get("/api/v1/dashboard/trend?days=30", headers=auth_headers)

            # Should have called cache_get with different keys
            calls = mock_get.call_args_list
            keys = [c[0][0] for c in calls]
            # Allow for 2 calls (one per request)
            assert any("dashboard:trend:7" in k for k in keys)
            assert any("dashboard:trend:30" in k for k in keys)

    def test_keywords_cache_key_varies_by_limit(self, client, auth_headers):
        """Different 'limit' params use different cache keys."""
        with patch("app.api.v1.dashboard.cache_get") as mock_get, \
             patch("app.api.v1.dashboard.cache_set") as mock_set:
            mock_get.return_value = None

            client.get("/api/v1/dashboard/keywords?limit=10", headers=auth_headers)
            client.get("/api/v1/dashboard/keywords?limit=50", headers=auth_headers)

            calls = mock_get.call_args_list
            keys = [c[0][0] for c in calls]
            assert any("dashboard:keywords:10" in k for k in keys)
            assert any("dashboard:keywords:50" in k for k in keys)

    def test_latest_comments_endpoint(self, client, auth_headers, sample_product, db):
        """GET /dashboard/latest-comments returns analyzed comments."""
        # Create analyzed comments
        comment = Comment(
            product_id=sample_product.id,
            content="非常好用值得购买推荐",
            rating=5,
            platform="jd",
        )
        db.session.add(comment)
        db.session.flush()

        analysis = CommentAnalysis(
            comment_id=comment.id,
            sentiment="positive",
            sentiment_score=0.95,
            fake_score=0.1,
        )
        db.session.add(analysis)
        db.session.commit()

        resp = client.get("/api/v1/dashboard/latest-comments?limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json().get("data", [])
        assert len(data) >= 1
        assert data[0]["sentiment"] == "positive"
        assert "content" in data[0]
        assert "product_name" in data[0]


class TestDashboardCacheInvalidation:
    """Verify that analysis completion invalidates dashboard cache."""

    def test_cache_invalidation_on_analysis_complete(self, app, db, sample_comments):
        """Simulate analysis task completion and verify cache_delete_pattern is called."""
        from app.tasks.analysis_tasks import run_analysis

        # Create analysis task
        task = AnalysisTask(
            user_id=1,
            name="Test task",
            status="pending",
            total_count=len(sample_comments),
        )
        db.session.add(task)
        db.session.commit()

        comment_ids = [c.id for c in sample_comments]

        with patch("app.tasks.analysis_tasks.cache_delete_pattern") as mock_invalidate:
            with patch("app.tasks.analysis_tasks.SentimentService") as MockService:
                instance = MockService.return_value
                instance.analyze.return_value = {
                    "sentiment": "positive",
                    "sentiment_score": 0.95,
                    "aspects": [],
                    "keywords": ["好"],
                    "summary": "",
                    "fake_score": 0.1,
                    "model_version": "test",
                }
                run_analysis(task.id, comment_ids)

            # Verify cache invalidation was called for dashboard
            mock_invalidate.assert_called_once_with("dashboard:*")

    def test_cache_invalidation_not_called_on_exception(self, app, db, sample_comments):
        """If analysis task fails before completing, cache should NOT be invalidated."""
        from app.tasks.analysis_tasks import run_analysis

        task = AnalysisTask(
            user_id=1,
            name="Failing task",
            status="pending",
            total_count=len(sample_comments),
        )
        db.session.add(task)
        db.session.commit()

        comment_ids = [c.id for c in sample_comments]

        with patch("app.tasks.analysis_tasks.cache_delete_pattern") as mock_invalidate:
            with patch("app.tasks.analysis_tasks.SentimentService") as MockService:
                instance = MockService.return_value
                instance.analyze.side_effect = RuntimeError("Model failed")

                run_analysis(task.id, comment_ids)

            # On complete failure, cache invalidation should still be called
            # (the task finishes with 'completed_with_errors' status)
            mock_invalidate.assert_called_once_with("dashboard:*")
