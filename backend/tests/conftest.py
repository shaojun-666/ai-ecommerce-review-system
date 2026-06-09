"""Test fixtures and configuration."""
import os

# Use in-memory Celery transport for testing (avoids Redis dependency)
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask
from app.models.product import Product


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 900
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 604800
    return app


@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def admin_user(db):
    user = User(
        username="admin",
        email="admin@test.com",
        role="admin",
        is_active=True,
    )
    user.set_password("admin123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def normal_user(db):
    user = User(
        username="user",
        email="user@test.com",
        role="user",
        is_active=True,
    )
    user.set_password("user123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_headers(client, normal_user):
    resp = client.post("/api/v1/auth/login", json={
        "username": "user",
        "password": "user123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, admin_user):
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_product(db, normal_user):
    product = Product(
        name="测试商品",
        platform="京东",
        user_id=normal_user.id,
    )
    db.session.add(product)
    db.session.commit()
    return product


@pytest.fixture
def sample_comments(db, sample_product):
    comments = []
    for i in range(5):
        c = Comment(
            product_id=sample_product.id,
            content=f"测试评论内容第{i+1}条，质量很好",
            rating=5,
            platform="京东",
            author_name=f"测试用户{i+1}",
        )
        db.session.add(c)
        comments.append(c)
    db.session.commit()
    return comments
