"""Seed database with demo data."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask
from datetime import datetime, timezone, timedelta


def seed():
    app = create_app("development")
    with app.app_context():
        db.create_all()

        # Check if already seeded
        if User.query.first():
            print("Database already seeded, skipping.")
            return

        # Users
        admin = User(username="admin", email="admin@example.com", role="admin", is_active=True)
        admin.set_password("admin123")
        user1 = User(username="user", email="user@example.com", role="user", is_active=True)
        user1.set_password("user123")
        db.session.add_all([admin, user1])
        db.session.flush()

        # Products
        products = [
            Product(name="iPhone 15 Pro Max", platform="京东", user_id=admin.id),
            Product(name="华为 Mate 60 Pro", platform="京东", user_id=admin.id),
            Product(name="小米14 Ultra", platform="淘宝", user_id=admin.id),
            Product(name="戴尔 XPS 16", platform="京东", user_id=user1.id),
            Product(name="SONY WH-1000XM5", platform="淘宝", user_id=user1.id),
        ]
        db.session.add_all(products)
        db.session.flush()

        # Comments with varied sentiment
        sample_comments = [
            # Positive
            Comment(product_id=products[0].id, content="手机性能非常好，A17 Pro芯片太强了，拍照效果也很棒，续航也不错，非常满意！", rating=5, platform="京东", author_name="数码达人"),
            Comment(product_id=products[0].id, content="物流很快，第二天就到了，手机包装完好，正品无误", rating=5, platform="京东", author_name="购物狂人"),
            Comment(product_id=products[1].id, content="华为拍照真的绝了，卫星通话功能很实用，支持国产！", rating=5, platform="京东", author_name="花粉用户"),
            Comment(product_id=products[1].id, content="信号比之前用的手机好太多了，电池耐用，一天一充", rating=5, platform="京东", author_name="商务精英"),
            Comment(product_id=products[2].id, content="性价比很高，这个价位能买到这么好的配置很值", rating=4, platform="淘宝", author_name="学生党"),
            Comment(product_id=products[3].id, content="XPS的屏幕素质一流，做工精致，重量控制得很好", rating=5, platform="京东", author_name="设计师小王"),
            Comment(product_id=products[4].id, content="降噪效果一流，戴上就听不见外界声音了，音质也很棒", rating=5, platform="淘宝", author_name="音乐爱好者"),
            # Negative
            Comment(product_id=products[0].id, content="发货太慢了，等了一周才到，客服态度也很差", rating=1, platform="京东", author_name="暴躁老哥"),
            Comment(product_id=products[1].id, content="价格太贵了，性价比不高，而且自带的广告太多了", rating=2, platform="京东", author_name="理性消费者"),
            Comment(product_id=products[2].id, content="用了三天就出现重启问题，品控有待提高", rating=1, platform="淘宝", author_name="倒霉蛋"),
            Comment(product_id=products[3].id, content="散热不行，轻度使用就发热，这个价位不应该", rating=2, platform="京东", author_name="技术控"),
            Comment(product_id=products[4].id, content="耳罩有点夹头，戴久了不舒服，而且蓝牙连接偶尔会断", rating=2, platform="淘宝", author_name="耳机发烧友"),
            # Neutral
            Comment(product_id=products[0].id, content="手机还行吧，就是价格有点贵，暂时没发现什么问题", rating=3, platform="京东", author_name="普通用户"),
            Comment(product_id=products[1].id, content="中规中矩，没有想象中那么好，但也不差", rating=3, platform="京东", author_name="中立派"),
        ]
        db.session.add_all(sample_comments)
        db.session.flush()

        # Analysis task with results
        task = AnalysisTask(
            user_id=admin.id,
            name="演示分析任务",
            status="completed",
            total_count=len(sample_comments),
            processed_count=len(sample_comments),
            failed_count=0,
            error_count=0,
            timeout_at=datetime.now(timezone.utc) + timedelta(hours=1),
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.session.add(task)
        db.session.flush()

        # Analysis results
        sentiment_map = {"positive": 0.92, "negative": 0.88, "neutral": 0.75}
        for i, c in enumerate(sample_comments):
            sentiment = "positive" if c.rating >= 4 else "negative" if c.rating <= 2 else "neutral"
            analysis = CommentAnalysis(
                comment_id=c.id,
                task_id=task.id,
                sentiment=sentiment,
                sentiment_score=sentiment_map[sentiment],
                aspects={"quality": 0.8, "logistics": 0.6, "service": 0.5, "price": 0.7},
                keywords=["质量", "性能", "性价比"] if sentiment == "positive" else ["价格", "服务", "物流"],
                summary=f"{'非常满意' if sentiment == 'positive' else '需要改进' if sentiment == 'negative' else '一般'}的商品评价",
                fake_score=0.05 if sentiment == "positive" else 0.1,
                model_version="bert-base-chinese-v1.0",
                analyzed_at=datetime.now(timezone.utc),
            )
            db.session.add(analysis)

        db.session.commit()
        print(f"Seed complete! Created users, {len(products)} products, {len(sample_comments)} comments, 1 task.")


if __name__ == "__main__":
    seed()
