"""Alert detection and management service."""
import logging
from datetime import datetime, timezone, timedelta
from app.extensions import db, get_redis
from app.models.alert import Alert
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.product_price import ProductPrice

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


# ─── Detection ──────────────────────────────────────────────────────

def check_negative_surge():
    """Detect products with sudden negative sentiment increase and create alerts."""
    now = _utcnow()
    recent = now - timedelta(days=7)
    prev = now - timedelta(days=14)
    created = []

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
            change_pct = int((recent_negative - prev_negative) / prev_negative * 100)
            alert = _create_unique_alert(
                product_id=p.id,
                alert_type="negative_surge",
                severity="warning",
                title=f"「{p.name}」负面评论激增",
                message=f"最近7天负面评论{recent_negative}条，环比增加{change_pct}%",
                detail={"recent_count": recent_negative, "prev_count": prev_negative, "change_pct": change_pct},
            )
            if alert:
                created.append(alert)
    return created


def check_price_anomalies():
    """Detect significant price changes across all products."""
    now = _utcnow()
    cutoff = now - timedelta(days=30)
    created = []

    products = Product.query.all()
    for p in products:
        latest = p.prices.first()
        if not latest:
            continue

        older = ProductPrice.query.filter(
            ProductPrice.product_id == p.id,
            ProductPrice.recorded_at < cutoff,
        ).order_by(ProductPrice.recorded_at.desc()).first()

        if not older:
            continue

        change_pct = round((latest.price - older.price) / older.price * 100, 1)
        if change_pct <= -15:
            alert = _create_unique_alert(
                product_id=p.id,
                alert_type="price_drop",
                severity="info",
                title=f"「{p.name}」价格大幅下跌",
                message=f"30天内从¥{older.price}降至¥{latest.price}（{change_pct}%）",
                detail={"old_price": older.price, "new_price": latest.price, "change_pct": change_pct},
            )
            if alert:
                created.append(alert)
        elif change_pct >= 20:
            alert = _create_unique_alert(
                product_id=p.id,
                alert_type="price_spike",
                severity="warning",
                title=f"「{p.name}」价格大幅上涨",
                message=f"30天内从¥{older.price}涨至¥{latest.price}（+{change_pct}%）",
                detail={"old_price": older.price, "new_price": latest.price, "change_pct": change_pct},
            )
            if alert:
                created.append(alert)

    return created


def check_silent_products():
    """Alert if products have no new comments in 14 days."""
    now = _utcnow()
    cutoff = now - timedelta(days=14)
    created = []

    silent_products = Product.query.filter(~Product.comments.any(
        Comment.created_at >= cutoff,
    )).all()

    for p in silent_products:
        alert = _create_unique_alert(
            product_id=p.id,
            alert_type="crawl_failure",
            severity="info",
            title=f"「{p.name}」超过14天无新评论",
            message="请检查爬虫配置或数据源是否正常",
            detail={"last_comment_cutoff": cutoff.isoformat()},
        )
        if alert:
            created.append(alert)

    return created


def _create_unique_alert(product_id, alert_type, severity, title, message, detail=None):
    """Create alert only if no identical alert exists in the last 24h (dedup)."""
    existing = Alert.query.filter(
        Alert.product_id == product_id,
        Alert.alert_type == alert_type,
        Alert.created_at >= _utcnow() - timedelta(hours=24),
    ).first()
    if existing:
        return None

    alert = Alert(
        product_id=product_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        detail=detail or {},
    )
    db.session.add(alert)
    db.session.commit()
    logger.info("Alert created: %s (product=%s, type=%s)", title, product_id, alert_type)
    return alert


# ─── Management ──────────────────────────────────────────────────────

def get_alerts(limit=50, unread_only=False):
    """Get recent alerts."""
    q = Alert.query.order_by(Alert.created_at.desc())
    if unread_only:
        q = q.filter(Alert.is_read == False)
    return q.limit(limit).all()


def mark_alert_read(alert_id):
    """Mark a single alert as read."""
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return False
    alert.is_read = True
    db.session.commit()
    return True


def mark_all_alerts_read():
    """Mark all unread alerts as read."""
    count = Alert.query.filter(Alert.is_read == False).update({"is_read": True})
    db.session.commit()
    return count


def get_unread_count():
    return Alert.query.filter(Alert.is_read == False).count()


def run_all_checks():
    """Run all alert checks and return summary."""
    results = {"negative_surge": [], "price_anomalies": [], "silent_products": []}
    try:
        results["negative_surge"] = [a.to_dict() for a in check_negative_surge()]
    except Exception as e:
        logger.error("check_negative_surge failed: %s", e)
    try:
        results["price_anomalies"] = [a.to_dict() for a in check_price_anomalies()]
    except Exception as e:
        logger.error("check_price_anomalies failed: %s", e)
    try:
        results["silent_products"] = [a.to_dict() for a in check_silent_products()]
    except Exception as e:
        logger.error("check_silent_products failed: %s", e)
    return results
