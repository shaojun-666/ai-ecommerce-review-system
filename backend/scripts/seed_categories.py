#!/usr/bin/env python3
"""Seed default categories into the database.

Usage:
    python scripts/seed_categories.py
"""
import logging
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("FLASK_ENV", "development")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_categories")


# Category tree: (slug, name, icon, children[(slug, name, icon, children...)])
CATEGORY_TREE = [
    ("digital", "数码电子", "📱", [
        ("phone", "手机", "📱", []),
        ("tablet", "平板电脑", "📟", []),
        ("laptop", "笔记本电脑", "💻", []),
        ("headphones", "耳机/耳麦", "🎧", []),
        ("smartwatch", "智能手表", "⌚", []),
        ("camera", "相机/摄影", "📷", []),
        ("phone-case", "手机配件", "🔌", []),
        ("speaker", "音箱/音响", "🔊", []),
    ]),
    ("clothing", "服装鞋包", "👗", [
        ("clothing", "服装", "👕", []),
        ("shoes", "鞋靴", "👟", []),
        ("bag", "箱包", "👜", []),
        ("accessories", "配饰", "💍", []),
        ("watch", "手表/腕表", "⌚", []),
    ]),
    ("home", "家居生活", "🏠", [
        ("furniture", "家具", "🛋️", []),
        ("home-textile", "家纺布艺", "🛏️", []),
        ("kitchen", "厨房用品", "🍳", []),
        ("home-appliance", "家用电器", "🔌", []),
        ("cleaning", "清洁用品", "🧹", []),
    ]),
    ("food", "食品饮料", "🍎", [
        ("food", "休闲食品", "🍪", []),
        ("tea", "茶叶", "🍵", []),
        ("alcohol", "酒类", "🍷", []),
    ]),
    ("beauty", "美妆个护", "💄", [
        ("skincare", "护肤", "🧴", []),
        ("cosmetics", "彩妆", "💄", []),
        ("hair-care", "头发护理", "💇", []),
        ("personal-care", "个护清洁", "🪥", []),
    ]),
    ("sports", "运动户外", "🏃", [
        ("sports", "运动健身", "🏋️", []),
        ("outdoor", "户外装备", "⛺", []),
        ("cycling", "骑行运动", "🚴", []),
    ]),
    ("entertainment", "图书娱乐", "📚", [
        ("books", "图书/教育", "📚", []),
        ("toys", "玩具", "🧸", []),
    ]),
    ("baby", "母婴宠物", "👶", [
        ("baby", "母婴用品", "🍼", []),
        ("pet", "宠物用品", "🐾", []),
    ]),
    ("office", "办公文具", "✏️", [
        ("office", "办公耗材", "🖨️", []),
    ]),
    ("auto", "汽车用品", "🚗", [
        ("auto", "汽车配件", "🚗", []),
    ]),
]


def seed():
    from app import create_app
    from app.extensions import db
    from app.models.category import Category

    app = create_app(os.getenv("APP_CONFIG", "development"))

    with app.app_context():
        existing = Category.query.count()
        if existing > 0:
            logger.info("Categories already seeded (%d existing), skipping.", existing)
            return

        def _insert(slug, name, icon, parent_id, level):
            cat = Category(slug=slug, name=name, icon=icon, parent_id=parent_id, level=level)
            db.session.add(cat)
            db.session.flush()  # get id
            return cat.id

        for p_slug, p_name, p_icon, children in CATEGORY_TREE:
            parent_id = _insert(p_slug, p_name, p_icon, None, 0)
            for c_slug, c_name, c_icon, _ in children:
                _insert(c_slug, c_name, c_icon, parent_id, 1)

        db.session.commit()
        logger.info("Seeded %d parent + child categories.", sum(1 + len(c[3]) for c in CATEGORY_TREE))


if __name__ == "__main__":
    seed()
