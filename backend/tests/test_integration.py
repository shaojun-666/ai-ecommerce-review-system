"""End-to-end integration tests for the full API flow.

Covers: auth lifecycle, product CRUD, comment operations, analysis tasks,
dashboard endpoints, and authorization boundaries.
"""

from unittest.mock import patch

import io
import json


class TestAuthFlow:
    """Full authentication lifecycle."""

    def test_login_success(self, client, normal_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "user123",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert "user" in body
        assert body["user"]["username"] == "user"

    def test_login_invalid_credentials(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 400

        resp = client.post("/api/v1/auth/login", json={"username": "user"})
        assert resp.status_code == 400

    def test_login_disabled_user(self, client, db, normal_user):
        normal_user.is_active = False
        db.session.commit()
        resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "user123",
        })
        assert resp.status_code == 403

    def test_refresh_token_success(self, client, normal_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "username": "user", "password": "user123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert resp.status_code == 401

    def test_refresh_missing_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 400

    def test_get_current_user(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "user"

    def test_unauthorized_access(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

        resp = client.get("/api/v1/products")
        assert resp.status_code == 401


class TestProductFlow:
    """Product CRUD and authorization."""

    def test_create_product(self, client, auth_headers):
        resp = client.post("/api/v1/products", headers=auth_headers, json={
            "name": "全新测试商品",
            "platform": "淘宝",
            "url": "https://example.com/product",
        })
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["name"] == "全新测试商品"
        assert data["platform"] == "淘宝"

    def test_create_product_no_name(self, client, auth_headers):
        resp = client.post("/api/v1/products", headers=auth_headers, json={})
        assert resp.status_code == 422

    def test_list_products(self, client, auth_headers, sample_product):
        resp = client.get("/api/v1/products", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) >= 1
        assert "meta" in data

    def test_get_product(self, client, auth_headers, sample_product):
        resp = client.get(f"/api/v1/products/{sample_product.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "测试商品"

    def test_get_product_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/products/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_product(self, client, auth_headers, sample_product):
        resp = client.put(f"/api/v1/products/{sample_product.id}", headers=auth_headers, json={
            "name": "更新后的商品",
            "platform": "拼多多",
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "更新后的商品"

    def test_update_product_not_found(self, client, auth_headers):
        resp = client.put("/api/v1/products/99999", headers=auth_headers, json={"name": "nope"})
        assert resp.status_code == 404

    def test_delete_product_requires_admin(self, client, auth_headers, sample_product):
        """Non-admin users can delete their own products."""
        resp = client.delete(f"/api/v1/products/{sample_product.id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_delete_product_as_admin(self, client, admin_headers, sample_product):
        resp = client.delete(f"/api/v1/products/{sample_product.id}", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_product_not_found(self, client, admin_headers):
        resp = client.delete("/api/v1/products/99999", headers=admin_headers)
        assert resp.status_code == 404


class TestCommentFlow:
    """Comment listing, detail, deletion, and batch import."""

    def test_list_comments(self, client, auth_headers, sample_comments):
        resp = client.get("/api/v1/comments", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] >= 5
        assert len(body["items"]) >= 5

    def test_list_comments_filter_by_product(self, client, auth_headers, sample_comments, sample_product):
        resp = client.get(
            f"/api/v1/comments?product_id={sample_product.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 5

    def test_list_comments_filter_by_platform(self, client, auth_headers, sample_comments):
        resp = client.get("/api/v1/comments?platform=京东", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_comments_pagination(self, client, auth_headers, sample_comments):
        resp = client.get("/api/v1/comments?page=1&per_page=2", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["items"]) == 2
        assert body["per_page"] == 2

    def test_list_comments_empty_product(self, client, auth_headers):
        """Filtering for a product with no comments returns empty list."""
        resp = client.get("/api/v1/comments?product_id=99999", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0

    def test_get_comment(self, client, auth_headers, sample_comments):
        cid = sample_comments[0].id
        resp = client.get(f"/api/v1/comments/{cid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["content"] == sample_comments[0].content

    def test_get_comment_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/comments/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_comment(self, client, auth_headers, sample_comments):
        cid = sample_comments[0].id
        resp = client.delete(f"/api/v1/comments/{cid}", headers=auth_headers)
        assert resp.status_code == 200

        # Verify it's gone
        resp = client.get(f"/api/v1/comments/{cid}", headers=auth_headers)
        assert resp.status_code == 404

    def test_batch_import_no_file(self, client, auth_headers):
        resp = client.post("/api/v1/comments/batch", headers=auth_headers)
        assert resp.status_code == 400


@patch("app.tasks.analysis_tasks.run_analysis.delay")
class TestAnalysisTaskFlow:
    """Analysis task lifecycle."""

    def test_create_task_no_comment_ids(self, mock_delay, client, auth_headers):
        resp = client.post("/api/v1/tasks", headers=auth_headers, json={
            "name": "empty test",
            "comment_ids": [],
        })
        assert resp.status_code == 400
        mock_delay.assert_not_called()

    def test_create_task(self, mock_delay, client, auth_headers, sample_comments):
        mock_delay.return_value.id = "mock-celery-id"
        comment_ids = [c.id for c in sample_comments]
        resp = client.post("/api/v1/tasks", headers=auth_headers, json={
            "name": "E2E test task",
            "comment_ids": comment_ids,
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert "task" in body
        assert body["task"]["status"] == "pending"
        assert body["task"]["total_count"] == len(comment_ids)
        mock_delay.assert_called_once()

    def test_list_tasks(self, mock_delay, client, auth_headers, sample_comments):
        mock_delay.return_value.id = "mock-celery-id"
        comment_ids = [c.id for c in sample_comments]
        client.post("/api/v1/tasks", headers=auth_headers, json={
            "name": "list test",
            "comment_ids": comment_ids,
        })

        resp = client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] >= 1
        assert len(body["items"]) >= 1

    def test_get_task_not_found(self, mock_delay, client, auth_headers):
        resp = client.get("/api/v1/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_results_empty(self, mock_delay, client, auth_headers, sample_comments):
        """A newly created task has no analysis results yet."""
        mock_delay.return_value.id = "mock-celery-id"
        comment_ids = [c.id for c in sample_comments]
        create_resp = client.post("/api/v1/tasks", headers=auth_headers, json={
            "name": "results test",
            "comment_ids": comment_ids,
        })
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/v1/tasks/{task_id}/results", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 0
        assert body["items"] == []


class TestDashboardFlow:
    """Dashboard endpoints smoke tests."""

    def test_overview(self, client, auth_headers, sample_comments):
        resp = client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert resp.status_code == 200

    def test_trend_default(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/trend", headers=auth_headers)
        assert resp.status_code == 200

    def test_trend_with_days(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/trend?days=7", headers=auth_headers)
        assert resp.status_code == 200

    def test_trend_clamps_days(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/trend?days=9999", headers=auth_headers)
        assert resp.status_code == 200

    def test_keywords(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/keywords", headers=auth_headers)
        assert resp.status_code == 200

    def test_keywords_with_limit(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/keywords?limit=10", headers=auth_headers)
        assert resp.status_code == 200


class TestAuthorizationBoundaries:
    """Permission and access control edge cases."""

    def test_regular_user_cannot_access_admin_endpoints(self, client, auth_headers, db, normal_user):
        """Non-admin users cannot delete another user's product."""
        from app.models.product import Product
        other = Product(name="他人商品", platform="jd", user_id=9999)
        db.session.add(other)
        db.session.commit()
        resp = client.delete(f"/api/v1/products/{other.id}", headers=auth_headers)
        assert resp.status_code == 403

    def test_access_token_type_check(self, client, normal_user):
        """Using a refresh token as access token should fail."""
        login_resp = client.post("/api/v1/auth/login", json={
            "username": "user", "password": "user123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {refresh_token}",
        })
        assert resp.status_code == 401

    def test_bearer_token_format(self, client):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "InvalidFormat token123",
        })
        assert resp.status_code == 401

        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "",
        })
        assert resp.status_code == 401

    def test_empty_token(self, client):
        resp = client.get("/api/v1/products", headers={
            "Authorization": "Bearer ",
        })
        assert resp.status_code == 401

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
