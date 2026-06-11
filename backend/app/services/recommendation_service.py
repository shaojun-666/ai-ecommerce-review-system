"""Product selection recommendation engine.
Template-based recommendations, structured for easy LLM swap-in later."""
import logging
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.product_price import ProductPrice
from app.services.scoring_service import score_all_products, get_category_heat

logger = logging.getLogger(__name__)


def generate_recommendations():
    """Generate comprehensive product selection recommendations."""
    scored = score_all_products()
    uptrend = [s for s in scored if s.get("uptrend", {}).get("is_uptrend")]
    categories = get_category_heat()

    now = datetime.now(timezone.utc)

    recommendations = []
    insights = []
    alerts = []

    # --- Per-product recommendations ---
    for s in scored[:10]:
        dims = s["dimensions"]
        reasons = []

        if s.get("uptrend", {}).get("is_uptrend"):
            confidence = s["uptrend"]["confidence"]
            if confidence >= 70:
                reasons.append(f"强烈上行信号(置信度{confidence}%)")
            else:
                reasons.append(f"上行趋势(置信度{confidence}%)")

        if dims["sentiment"]["score"] >= 70:
            reasons.append(f"好评率{dims['sentiment']['score']}%")
        elif dims["sentiment"]["score"] < 30:
            reasons.append(f"好评率仅{dims['sentiment']['score']}%，需关注品质问题")

        if dims["growth"]["growth_rate"] and dims["growth"]["growth_rate"] > 30:
            reasons.append(f"评论激增{dims['growth']['growth_rate']}%")
        elif dims["growth"]["growth_rate"] and dims["growth"]["growth_rate"] < -30:
            reasons.append(f"评论量下降{dims['growth']['growth_rate']}%")

        if dims["price"]["trend"] == "stable":
            reasons.append("价格稳定")
        elif dims["price"]["trend"] == "up":
            reasons.append("价格上升趋势")

        product = db.session.get(Product, s["product_id"])
        tags = [t.name for t in product.tags] if product else []

        recommendation = {
            "product_id": s["product_id"],
            "product_name": s["product_name"],
            "composite_score": s["composite_score"],
            "reasons": reasons,
            "tags": tags or [],
            "action": _recommend_action(s),
        }
        recommendations.append(recommendation)

    # --- Category-level insights ---
    for cat in categories[:5]:
        if cat["heat_score"] >= 50:
            direction = "上升" if cat["comment_growth_rate"] > 0 else "下降"
            insights.append(
                f"品类「{cat['tag_name']}」热度{cat['heat_score']}分，评论量{direction}趋势"
                f"({cat['comment_growth_rate']:+.1f}%)，好评率{cat['positive_rate']}%"
            )

    # --- Alerts ---
    if uptrend:
        alerts.append(
            f"发现 {len(uptrend)} 个处于上行期的商品，建议优先关注评分最高的"
            f"「{uptrend[0]['product_name']}」"
        )

    # Check for silent products (no comments in 14 days)
    silent = Product.query.filter(~Product.comments.any(
        Comment.created_at >= now - timedelta(days=14),
    )).count()
    if silent > 0:
        alerts.append(f"有 {silent} 个商品超过14天无新评论，建议检查爬虫配置")

    # Check for sentiment alerts
    negative_surge = _check_negative_surge()
    if negative_surge:
        alerts.extend(negative_surge)

    return {
        "generated_at": now.isoformat(),
        "summary": _generate_summary(scored, uptrend, categories),
        "recommendations": recommendations[:10],
        "insights": insights[:10],
        "alerts": alerts[:5],
    }


def _recommend_action(score_data):
    """Determine recommended action based on scoring."""
    s = score_data["composite_score"]
    uptrend = score_data.get("uptrend", {})
    is_up = uptrend.get("is_uptrend", False)

    if s >= 80 and is_up:
        return {"action": "strong_buy", "label": "强烈推荐", "priority": 1}
    if s >= 60 and is_up:
        return {"action": "buy", "label": "推荐关注", "priority": 2}
    if s >= 50:
        return {"action": "watch", "label": "持续观察", "priority": 3}
    if s >= 30:
        return {"action": "review", "label": "需复核", "priority": 4}
    return {"action": "avoid", "label": "暂不推荐", "priority": 5}


def _check_negative_surge():
    """Detect products with sudden negative sentiment increase."""
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=7)
    prev = now - timedelta(days=14)

    alerts = []
    products = Product.query.all()
    for p in products:
        recent_negative = CommentAnalysis.query.join(Comment).filter(
            Comment.product_id == p.id,
            CommentAnalysis.sentiment == "negative",
            CommentAnalysis.analyzed_at >= recent,
        ).count()
        prev_negative = CommentAnalysis.query.join(Comment).filter(
            Comment.product_id == p.id,
            CommentAnalysis.sentiment == "negative",
            CommentAnalysis.analyzed_at >= prev,
            CommentAnalysis.analyzed_at < recent,
        ).count()

        if prev_negative > 0 and recent_negative > prev_negative * 1.5 and recent_negative >= 3:
            alerts.append(
                f"「{p.name}」负面评论激增(最近7天{recent_negative}条，"
                f"环比+{((recent_negative-prev_negative)/prev_negative*100):.0f}%)，建议及时关注"
            )

    return alerts


def _generate_summary(scored, uptrend, categories):
    """Generate a concise text summary of the current market situation."""
    total = len(scored)
    uptrend_count = len(uptrend)
    avg_score = round(sum(s["composite_score"] for s in scored) / total, 1) if total > 0 else 0
    hot_categories = [c["tag_name"] for c in categories[:3] if c["heat_score"] >= 50]

    parts = [f"当前共监控 {total} 个商品，综合评分均值 {avg_score}"]
    if uptrend_count:
        parts.append(f"发现 {uptrend_count} 个处于上行期的商品")
    else:
        parts.append("暂未检测到明确上行期商品")

    if hot_categories:
        parts.append(f"热门品类: {'、'.join(hot_categories)}")

    return "。".join(parts) + "。"
