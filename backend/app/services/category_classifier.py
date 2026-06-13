"""Category classifier — keyword-based auto-classification for products.

Uses a rule-based keyword matching approach:
  1. Match product name against keyword rules
  2. Fall back to platform-specific category mapping
  3. Default to "uncategorized"

Extensible: rules can be loaded from DB or config.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in keyword rules: (category_slug, [keywords], priority)
# Higher priority wins when multiple rules match.
# ---------------------------------------------------------------------------
_KEYWORD_RULES: list[tuple[str, list[str], int]] = [
    # Digital / Electronics
    ("phone", ["手机", "iphone", "智能手机", "phone", "小米", "华为", "荣耀", "oppo", "vivo"], 100),
    ("tablet", ["平板", "ipad", "pad", "tablet"], 100),
    ("laptop", ["笔记本", "电脑", "laptop", "macbook", "thinkpad", "游戏本"], 100),
    ("headphones", ["耳机", "earphone", "headphone", "airpods", "蓝牙耳机"], 100),
    ("smartwatch", ["手表", "watch", "智能手表", "手环", "band"], 90),
    ("camera", ["相机", "摄像头", "camera", "摄影", "单反"], 90),
    ("phone-case", ["手机壳", "手机膜", "手机配件", "充电器", "充电宝", "数据线", "power bank"], 80),
    ("speaker", ["音箱", "音响", "speaker", "soundbar"], 90),

    # Clothing / Fashion
    ("clothing", ["服装", "衣服", "上衣", "裤子", "裙子", "连衣裙", "t恤", "衬衫", "外套", "夹克"], 90),
    ("shoes", ["鞋", "运动鞋", "休闲鞋", "皮鞋", "靴子", "sneaker", "跑鞋"], 90),
    ("bag", ["包", "背包", "手提包", "斜挎包", "双肩包", "书包"], 90),
    ("accessories", ["配饰", "首饰", "项链", "手链", "戒指", "耳环", "眼镜", "墨镜"], 80),
    ("watch", ["手表", "腕表", "石英表", "机械表"], 90),

    # Home / Furniture
    ("furniture", ["家具", "沙发", "床", "桌子", "椅子", "柜子", "书架", "茶几"], 90),
    ("home-textile", ["家纺", "床单", "被套", "枕头", "被子", "四件套", "毛巾"], 90),
    ("kitchen", ["厨房", "厨具", "锅", "刀具", "餐具", "碗", "杯子", "水壶"], 90),
    ("home-appliance", ["家电", "冰箱", "洗衣机", "空调", "电视", "微波炉", "电饭煲", "烤箱"], 100),
    ("cleaning", ["清洁", "吸尘器", "扫地机", "拖把", "洗地机", "机器人"], 90),

    # Food / Grocery
    ("food", ["食品", "零食", "饮料", "酒", "茶叶", "咖啡", "牛奶", "坚果", "巧克力"], 80),
    ("tea", ["茶叶", "红茶", "绿茶", "乌龙茶", "普洱茶", "龙井"], 90),
    ("alcohol", ["白酒", "红酒", "啤酒", "洋酒", "葡萄酒", "威士忌"], 90),

    # Beauty / Personal Care
    ("skincare", ["护肤", "面霜", "精华", "面膜", "防晒", "眼霜", "水乳"], 90),
    ("cosmetics", ["彩妆", "口红", "粉底", "眼影", "腮红", "眉笔", "化妆"], 90),
    ("hair-care", ["洗发", "护发", "染发", "吹风机", "理发"], 80),
    ("personal-care", ["个护", "牙刷", "牙膏", "电动牙刷", "剃须刀", "冲牙器"], 80),

    # Sports / Outdoors
    ("sports", ["运动", "健身", "瑜伽", "哑铃", "跑步机", "健身器材"], 80),
    ("outdoor", ["户外", "露营", "帐篷", "登山", "背包", "野餐", "折叠椅"], 90),
    ("cycling", ["自行车", "骑行", "电动车", "平衡车"], 90),

    # Books / Media
    ("books", ["书", "书籍", "图书", "小说", "教材", "绘本", "文学"], 80),

    # Toys / Baby
    ("toys", ["玩具", "积木", "遥控", "模型", "乐高", "拼图"], 80),
    ("baby", ["婴儿", "母婴", "奶粉", "尿不湿", "奶瓶", "宝宝", "儿童"], 90),
    ("pet", ["宠物", "猫粮", "狗粮", "猫砂", "宠物用品"], 90),

    # Office / Stationery
    ("office", ["办公", "文具", "笔", "纸张", "文件夹", "打印机", "耗材"], 80),

    # Automotive
    ("auto", ["汽车", "车载", "车品", "行车记录仪", "座垫", "轮胎", "机油"], 90),

    # Uncategorized fallback
    ("uncategorized", [], 0),
]

# Compile keyword patterns once
_KEYWORD_PATTERNS = [
    (slug, re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE), priority)
    for slug, kws, priority in _KEYWORD_RULES
    if kws
]


def classify_product_name(name: str) -> str:
    """Classify a product name into a category slug.

    Returns the best-matching category slug, or "uncategorized".
    """
    if not name:
        return "uncategorized"

    best_slug = "uncategorized"
    best_priority = 0

    for slug, pattern, priority in _KEYWORD_PATTERNS:
        if priority <= best_priority:
            continue
        if pattern.search(name):
            best_slug = slug
            best_priority = priority

    return best_slug


def auto_categorize_product(product_id: int) -> Optional[str]:
    """Auto-categorize a product by its name and persist the mapping.

    Returns the assigned category slug, or None if no category matched.
    """
    from app.extensions import db
    from app.models.product import Product
    from app.models.category import Category, product_category_map

    product = Product.query.get(product_id)
    if not product:
        logger.warning("Product %d not found", product_id)
        return None

    slug = classify_product_name(product.name)
    if slug == "uncategorized":
        logger.info("Product %d (%s) uncategorized", product_id, product.name)
        return None

    category = Category.query.filter_by(slug=slug).first()
    if not category:
        logger.warning("Category slug %r not found in DB", slug)
        return None

    # Check if already mapped
    existing = db.session.execute(
        product_category_map.select().where(
            product_category_map.c.product_id == product_id,
            product_category_map.c.category_id == category.id,
        )
    ).first()
    if existing:
        return slug

    db.session.execute(
        product_category_map.insert().values(product_id=product_id, category_id=category.id)
    )
    db.session.commit()
    logger.info("Product %d → category %s", product_id, slug)
    return slug


def batch_categorize_all(commit: bool = True) -> dict:
    """Run auto-categorization on all products without a category.

    Returns stats dict.
    """
    from app.extensions import db
    from app.models.product import Product
    from app.models.category import product_category_map

    # Find products without any category mapping
    uncategorized = db.session.query(Product).outerjoin(
        product_category_map, Product.id == product_category_map.c.product_id
    ).filter(product_category_map.c.product_id == None).all()

    stats = {"total": len(uncategorized), "categorized": 0, "errors": 0}
    for product in uncategorized:
        try:
            result = auto_categorize_product(product.id)
            if result:
                stats["categorized"] += 1
        except Exception as e:
            logger.error("Failed to categorize product %d: %s", product.id, e)
            stats["errors"] += 1

    if commit:
        db.session.commit()

    return stats
