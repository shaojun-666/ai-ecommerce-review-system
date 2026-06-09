"""Tests for API endpoints."""


class TestProductsAPI:
    def test_list_products(self, client, auth_headers, sample_product):
        resp = client.get("/api/v1/products", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) >= 1

    def test_create_product(self, client, auth_headers):
        resp = client.post("/api/v1/products", headers=auth_headers, json={
            "name": "新商品",
            "platform": "淘宝",
        })
        assert resp.status_code == 201
        assert resp.get_json()["data"]["name"] == "新商品"

    def test_create_product_no_name(self, client, auth_headers):
        resp = client.post("/api/v1/products", headers=auth_headers, json={})
        assert resp.status_code == 422

    def test_get_product(self, client, auth_headers, sample_product):
        resp = client.get(f"/api/v1/products/{sample_product.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "测试商品"

    def test_get_product_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/products/9999", headers=auth_headers)
        assert resp.status_code == 404


class TestCommentsAPI:
    def test_list_comments(self, client, auth_headers, sample_comments):
        resp = client.get("/api/v1/comments", headers=auth_headers)
        assert resp.status_code == 200

    def test_delete_comment(self, client, auth_headers, sample_comments):
        cid = sample_comments[0].id
        resp = client.delete(f"/api/v1/comments/{cid}", headers=auth_headers)
        assert resp.status_code == 200


class TestDashboardAPI:
    def test_overview(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert resp.status_code == 200

    def test_trend(self, client, auth_headers):
        resp = client.get("/api/v1/dashboard/trend", headers=auth_headers)
        assert resp.status_code == 200
