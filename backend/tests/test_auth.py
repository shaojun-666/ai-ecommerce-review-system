"""Tests for authentication endpoints."""


class TestAuthLogin:
    def test_login_success(self, client, normal_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "user123",
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_password(self, client, normal_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "nobody",
            "password": "pass123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "test"})
        assert resp.status_code == 400


class TestAuthMe:
    def test_get_profile(self, client, auth_headers, normal_user):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["user"]["username"] == "user"
        assert data["user"]["email"] == "user@test.com"

    def test_get_profile_unauthorized(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestAuthRefresh:
    def test_refresh_token(self, client, normal_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "user123",
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
