"""Tests for database models."""
from app.models.user import User
from app.models.comment import Comment, CommentAnalysis
from app.models.product import Product
from app.models.analysis_task import AnalysisTask


class TestUserModel:
    def test_create_user(self, db):
        user = User(username="testuser", email="test@test.com", role="user")
        user.set_password("test123")
        db.session.add(user)
        db.session.commit()

        saved = db.session.get(User, user.id)
        assert saved.username == "testuser"
        assert saved.check_password("test123")
        assert not saved.check_password("wrong")

    def test_to_dict(self, db):
        user = User(username="test", email="t@t.com", role="admin")
        user.set_password("test123")
        db.session.add(user)
        db.session.commit()
        d = user.to_dict()
        assert d["username"] == "test"
        assert d["role"] == "admin"
        assert "password_hash" not in d


class TestProductModel:
    def test_create_product(self, db):
        product = Product(name="测试商品", platform="京东")
        db.session.add(product)
        db.session.commit()
        assert product.id is not None
        assert product.to_dict()["name"] == "测试商品"


class TestCommentModel:
    def test_create_comment(self, db, sample_product):
        comment = Comment(
            product_id=sample_product.id,
            content="质量非常好",
            rating=5,
        )
        db.session.add(comment)
        db.session.commit()
        assert comment.id is not None

    def test_comment_analysis_relationship(self, db, sample_comments):
        comment = sample_comments[0]
        analysis = CommentAnalysis(
            comment_id=comment.id,
            sentiment="positive",
            sentiment_score=0.95,
            fake_score=0.1,
        )
        db.session.add(analysis)
        db.session.commit()
        assert comment.analysis is not None
        assert comment.analysis.sentiment == "positive"


class TestAnalysisTaskModel:
    def test_create_task(self, db, admin_user):
        task = AnalysisTask(
            user_id=admin_user.id,
            name="测试任务",
            status="pending",
            total_count=100,
        )
        db.session.add(task)
        db.session.commit()
        assert task.id is not None
        assert task.to_dict()["status"] == "pending"
