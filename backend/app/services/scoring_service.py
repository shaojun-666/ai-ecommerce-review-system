"""Multi-dimensional product scoring and uptrend detection engine."""
import logging
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.product_price import ProductPrice

logger = logging.getLogger(__name__)

# Scoring weights
W_SENTIMENT = 0.30
W_GROWTH = 0.30
W_PRICE = 0.20
W_ACTIVITY = 0.20

# Uptrend thresholds
GROWTH_SURGE_THRESHOLD = 20.0
POSITIVE_RATE_THRESHOLD = 60.0
PRICE_VOLATILITY_MAX = 15.0
STALE_DAYS = 7
MIN_COMMENT_VELOCITY = 5
UPTREND_SIGNAL_MIN = 3
UPTREND_SCORE_MIN = 50


def score_product(product, weights=None):
    """Compute multi-dimensional scores for a single product."""
    w = weights or {}
    w_s = w.get("sentiment", W_SENTIMENT)
    w_g = w.get("growth", W_GROWTH)
    w_p = w.get("price", W_PRICE)
    w_a = w.get("activity", W_ACTIVITY)
    now = datetime.now(timezone.utc)

    # --- Sentiment score ---
    positive_count = CommentAnalysis.query.join(Comment).filter(
        Comment.product_id == product.id,
        CommentAnalysis.sentiment == "positive",
    ).count()
    total_analyzed = CommentAnalysis.query.join(Comment).filter(
        Comment.product_id == product.id,
    ).count()
    sentiment_score = round(positive_count / total_analyzed * 100, 1) if total_analyzed > 0 else 0

    # --- Comment growth score ---
    period_start = now - timedelta(days=14)
    prev_period_start = now - timedelta(days=28)
    current_count = Comment.query.filter(
        Comment.product_id == product.id,
        Comment.created_at >= period_start,
    ).count()
    prev_count = Comment.query.filter(
        Comment.product_id == product.id,
        Comment.created_at >= prev_period_start,
        Comment.created_at < period_start,
    ).count()
    growth_rate = ((current_count - prev_count) / prev_count * 100) if prev_count > 0 else 0
    growth_score = max(0, min(100, 50 + growth_rate))

    # --- Price score (stability + trend) ---
    price_records = ProductPrice.query.filter(
        ProductPrice.product_id == product.id,
        ProductPrice.recorded_at >= now - timedelta(days=30),
    ).order_by(ProductPrice.recorded_at.asc()).all()

    price_score = 50.0
    price_trend = "stable"
    if len(price_records) >= 2:
        prices = [p.price for p in price_records]
        avg_price = sum(prices) / len(prices)
        volatility = ((max(prices) - min(prices)) / avg_price * 100) if avg_price > 0 else 0
        first_price = price_records[0].price
        last_price = price_records[-1].price
        change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0
        # Stable price with slight upward trend is ideal
        if volatility < 10 and -5 <= change_pct <= 10:
            price_score = 80 + max(0, change_pct * 2)
        elif volatility < 20 and change_pct > -10:
            price_score = 50
        else:
            price_score = max(0, 50 - volatility)
        price_score = max(0, min(100, price_score))
        price_trend = "up" if change_pct > 5 else ("down" if change_pct < -5 else "stable")

    # --- Activity score (recency) ---
    last_comment = Comment.query.filter(
        Comment.product_id == product.id,
    ).order_by(Comment.created_at.desc()).first()

    if last_comment and last_comment.created_at:
        days_since = (now - last_comment.created_at).days
        activity_score = max(0, 100 - days_since * 15)
    else:
        activity_score = 0

    composite = round(w_s * sentiment_score + w_g * growth_score + w_p * price_score + w_a * activity_score, 1)

    latest_price = None
    latest_price_record = product.prices.first()
    if latest_price_record:
        latest_price = latest_price_record.price

    return {
        "product_id": product.id,
        "product_name": product.name,
        "platform": product.platform,
        "composite_score": composite,
        "dimensions": {
            "sentiment": {"score": sentiment_score, "weight": w_s},
            "growth": {"score": growth_score, "weight": w_g, "growth_rate": round(growth_rate, 1)},
            "price": {"score": price_score, "weight": w_p, "trend": price_trend},
            "activity": {"score": activity_score, "weight": w_a},
        },
        "latest_price": latest_price,
    }


def detect_uptrend(product, scores=None):
    """Detect whether a product is in an uptrend phase."""
    if scores is None:
        scores = score_product(product)

    dims = scores["dimensions"]
    now = datetime.now(timezone.utc)

    growth_rate = dims["growth"]["growth_rate"]
    sentiment_score = dims["sentiment"]["score"]
    price_trend = dims["price"]["trend"]

    signals = {}

    # Signal 1: comment growth surge
    signals["comment_growth_surge"] = growth_rate > GROWTH_SURGE_THRESHOLD

    # Signal 2: positive sentiment
    signals["sentiment_positive"] = sentiment_score > POSITIVE_RATE_THRESHOLD

    # Signal 3: price stability
    signals["price_stable"] = dims["price"]["score"] >= 50

    # Signal 4: recent activity
    last_comment = Comment.query.filter(
        Comment.product_id == product.id,
    ).order_by(Comment.created_at.desc()).first()
    if last_comment and last_comment.created_at:
        days_since = (now - last_comment.created_at).days
        signals["recent_activity"] = days_since <= STALE_DAYS
    else:
        signals["recent_activity"] = False

    # Signal 5: comment velocity
    recent_count = Comment.query.filter(
        Comment.product_id == product.id,
        Comment.created_at >= now - timedelta(days=14),
    ).count()
    signals["comment_velocity"] = recent_count >= MIN_COMMENT_VELOCITY

    active_signals = sum(1 for v in signals.values() if v)
    is_uptrend = active_signals >= UPTREND_SIGNAL_MIN and scores["composite_score"] >= UPTREND_SCORE_MIN
    confidence = round((active_signals / 5) * (scores["composite_score"] / 100) * 100, 1)

    return {
        "product_id": product.id,
        "product_name": product.name,
        "is_uptrend": is_uptrend,
        "confidence": min(confidence, 100),
        "active_signals": active_signals,
        "total_signals": 5,
        "signals": signals,
        "composite_score": scores["composite_score"],
    }


def score_all_products(weights=None, uptrend_only=False):
    """Score all products, optionally filtering to uptrend only."""
    products = Product.query.order_by(Product.created_at.desc()).all()
    results = []
    for p in products:
        s = score_product(p, weights)
        if uptrend_only:
            u = detect_uptrend(p, s)
            s["uptrend"] = u
            if not u["is_uptrend"]:
                continue
        results.append(s)

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


def get_category_heat(tag_id=None, days=30):
    """Aggregate comment/sentiment heat by category (tag)."""
    from app.models.product_tag import ProductTag, product_tag_map

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    prev_since = now - timedelta(days=days * 2)

    query = ProductTag.query
    if tag_id:
        query = query.filter(ProductTag.id == tag_id)
    tags = query.all()

    results = []
    for tag in tags:
        product_ids = [
            row[0] for row in
            db.session.query(product_tag_map.c.product_id).filter(
                product_tag_map.c.tag_id == tag.id
            ).all()
        ]
        if not product_ids:
            continue

        # Current period comments
        current_count = Comment.query.filter(
            Comment.product_id.in_(product_ids),
            Comment.created_at >= since,
        ).count()

        # Previous period comments
        prev_count = Comment.query.filter(
            Comment.product_id.in_(product_ids),
            Comment.created_at >= prev_since,
            Comment.created_at < since,
        ).count()

        growth_rate = round((current_count - prev_count) / prev_count * 100, 1) if prev_count > 0 else 0

        # Sentiment for this category
        positive = CommentAnalysis.query.join(Comment).filter(
            Comment.product_id.in_(product_ids),
            CommentAnalysis.sentiment == "positive",
        ).count()
        negative = CommentAnalysis.query.join(Comment).filter(
            Comment.product_id.in_(product_ids),
            CommentAnalysis.sentiment == "negative",
        ).count()
        total_sentiment = CommentAnalysis.query.join(Comment).filter(
            Comment.product_id.in_(product_ids),
        ).count()

        positive_rate = round(positive / total_sentiment * 100, 1) if total_sentiment > 0 else 0

        # Product count in category
        product_count = len(product_ids)

        # New products in period
        new_products = Product.query.filter(
            Product.tags.any(id=tag.id),
            Product.created_at >= since,
        ).count()

        results.append({
            "tag_id": tag.id,
            "tag_name": tag.name,
            "tag_color": tag.color,
            "product_count": product_count,
            "comment_count": current_count,
            "comment_growth_rate": growth_rate,
            "positive_rate": positive_rate,
            "sentiment_count": {"positive": positive, "negative": negative},
            "new_products": new_products,
            "heat_score": round(
                (current_count * 0.3 + positive_rate * 0.3 + max(0, growth_rate) * 0.2 + new_products * 10 * 0.2),
                1,
            ),
        })

    results.sort(key=lambda x: x["heat_score"], reverse=True)
    return results
