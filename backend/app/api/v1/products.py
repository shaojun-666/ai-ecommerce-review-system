from datetime import timedelta
from flask import request
from app.extensions import db
from app.models.product import Product
from app.models.product_price import ProductPrice
from app.models.crawl_task import CrawlTask
from app.models.comment import Comment
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.utils.pagination import paginate_query
from app.utils.time import utcnow
from app.services.scoring_service import score_product, score_all_products, detect_uptrend, get_category_heat
from app.services.recommendation_service import generate_recommendations
from app.api.v1 import api_bp


@api_bp.route("/products", methods=["GET"])
@require_auth
def list_products(current_user):
    q = Product.query
    if search := request.args.get("q"):
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if tag_id := request.args.get("tag_id"):
        try:
            q = q.filter(Product.tags.any(id=int(tag_id)))
        except (ValueError, TypeError):
            pass
    q = q.order_by(Product.created_at.desc())
    if current_user.role != "admin":
        q = q.filter(db.or_(Product.user_id == current_user.id, Product.user_id.is_(None)))

    items, total, page, per_page = paginate_query(q)
    result = [_product_with_monitoring(p) for p in items]
    return success(
        result,
        meta={"page": page, "per_page": per_page, "total": total},
    )


@api_bp.route("/products/<int:product_id>", methods=["GET"])
@require_auth
def get_product(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    return success(_product_with_monitoring(product))


@api_bp.route("/products", methods=["POST"])
@require_auth
def create_product(current_user):
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("Product name is required", 422)

    product = Product(
        name=name,
        platform=data.get("platform", ""),
        url=data.get("url", ""),
        image_url=data.get("image_url", ""),
        user_id=current_user.id,
    )
    db.session.add(product)
    db.session.commit()
    return success(product.to_dict(), message="Product created", code=201)


@api_bp.route("/products/batch", methods=["POST"])
@require_auth
def batch_create_products(current_user):
    data = request.get_json(force=True) or {}
    items = data.get("items", [])
    if not items:
        return fail("No products provided", 422)

    created = []
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        product = Product(
            name=name,
            platform=item.get("platform", ""),
            url=item.get("url", ""),
            user_id=current_user.id,
        )
        db.session.add(product)
        created.append(product)

    db.session.commit()
    return success([p.to_dict() for p in created], message=f"{len(created)} products created", code=201)


@api_bp.route("/products/<int:product_id>", methods=["PUT"])
@require_auth
def update_product(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)

    data = request.get_json(force=True)
    if "name" in data:
        product.name = data["name"]
    if "platform" in data:
        product.platform = data["platform"]
    if "url" in data:
        product.url = data["url"]
    if "image_url" in data:
        product.image_url = data["image_url"]

    db.session.commit()
    return success(_product_with_monitoring(product))


@api_bp.route("/products/<int:product_id>", methods=["DELETE"])
@require_auth
def delete_product(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    if current_user.role != "admin" and product.user_id != current_user.id:
        return fail("Forbidden", 403)
    db.session.delete(product)
    db.session.commit()
    return success(message="Product deleted")


@api_bp.route("/products/<int:product_id>/prices", methods=["GET"])
@require_auth
def get_product_prices(current_user, product_id):
    """Return price history for a product."""
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)

    days = request.args.get("days", 90, type=int)
    since = utcnow() - timedelta(days=days)

    prices = ProductPrice.query.filter(
        ProductPrice.product_id == product_id,
        ProductPrice.recorded_at >= since,
    ).order_by(ProductPrice.recorded_at.asc()).all()

    latest_price_record = product.prices.first()

    return success({
        "product_id": product_id,
        "product_name": product.name,
        "current_price": latest_price_record.price if latest_price_record else None,
        "prices": [p.to_dict() for p in prices],
    })


@api_bp.route("/products/price-alerts", methods=["GET"])
@require_auth
def get_price_alerts(current_user):
    """Find products with significant price changes in the last 30 days."""
    q = Product.query
    if current_user.role != "admin":
        q = q.filter(db.or_(Product.user_id == current_user.id, Product.user_id.is_(None)))

    products = q.all()
    alerts = []

    for p in products:
        latest = p.prices.first()
        if not latest:
            continue

        # Get price 30 days ago or earliest available
        cutoff = utcnow() - timedelta(days=30)
        older = ProductPrice.query.filter(
            ProductPrice.product_id == p.id,
            ProductPrice.recorded_at < cutoff,
        ).order_by(ProductPrice.recorded_at.desc()).first()

        if not older:
            continue

        change_pct = round((latest.price - older.price) / older.price * 100, 1)
        if abs(change_pct) >= 5:
            alerts.append({
                "product_id": p.id,
                "product_name": p.name,
                "platform": p.platform,
                "old_price": older.price,
                "current_price": latest.price,
                "change_pct": change_pct,
                "direction": "up" if change_pct > 0 else "down",
                "old_date": older.recorded_at.isoformat() if older.recorded_at else None,
                "new_date": latest.recorded_at.isoformat() if latest.recorded_at else None,
            })

    alerts.sort(key=lambda a: abs(a["change_pct"]), reverse=True)
    return success(alerts)


@api_bp.route("/products/<int:product_id>/growth", methods=["GET"])
@require_auth
def get_product_growth(current_user, product_id):
    """Return comment growth rate as a sales proxy indicator."""
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)

    days = request.args.get("days", 14, type=int)
    now = utcnow()
    period_start = now - timedelta(days=days)
    prev_period_start = now - timedelta(days=days * 2)

    # Current period comment count
    current_count = Comment.query.filter(
        Comment.product_id == product_id,
        Comment.created_at >= period_start,
    ).count()

    # Previous period comment count
    prev_count = Comment.query.filter(
        Comment.product_id == product_id,
        Comment.created_at >= prev_period_start,
        Comment.created_at < period_start,
    ).count()

    growth_rate = None
    if prev_count > 0:
        growth_rate = round((current_count - prev_count) / prev_count * 100, 1)

    # Daily breakdown
    daily = db.session.query(
        db.func.date(Comment.created_at).label("date"),
        db.func.count(Comment.id).label("count"),
    ).filter(
        Comment.product_id == product_id,
        Comment.created_at >= prev_period_start,
    ).group_by(db.func.date(Comment.created_at)).order_by(db.func.date(Comment.created_at)).all()

    return success({
        "product_id": product_id,
        "product_name": product.name,
        "days": days,
        "current_period_count": current_count,
        "previous_period_count": prev_count,
        "growth_rate": growth_rate,
        "trend": "up" if growth_rate and growth_rate > 10 else ("down" if growth_rate and growth_rate < -10 else "stable"),
        "daily": [{"date": str(r.date), "count": r.count} for r in daily],
    })


@api_bp.route("/products/<int:product_id>/monitoring", methods=["GET"])
@require_auth
def get_product_monitoring(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    return success(_monitoring_info(product))


@api_bp.route("/products/scoring", methods=["GET"])
@require_auth
def product_scoring(current_user):
    uptrend_only = request.args.get("uptrend_only", "").lower() in ("1", "true", "yes")
    results = score_all_products(uptrend_only=uptrend_only)
    return success(results)


@api_bp.route("/products/<int:product_id>/score", methods=["GET"])
@require_auth
def product_score_detail(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    s = score_product(product)
    u = detect_uptrend(product, s)
    return success({"score": s, "uptrend": u})


@api_bp.route("/products/uptrend", methods=["GET"])
@require_auth
def product_uptrend(current_user):
    results = score_all_products(uptrend_only=True)
    return success(results)


@api_bp.route("/dashboard/category-heat", methods=["GET"])
@require_auth
def category_heat(current_user):
    tag_id = request.args.get("tag_id", type=int)
    days = request.args.get("days", 30, type=int)
    days = min(max(days, 1), 365)
    data = get_category_heat(tag_id=tag_id, days=days)
    return success(data)


@api_bp.route("/products/recommendations", methods=["GET"])
@require_auth
def product_recommendations(current_user):
    data = generate_recommendations()
    return success(data)


def _monitoring_info(product):
    """Return crawl task monitoring info for a product."""
    crawl_task = CrawlTask.query.filter_by(product_id=product.id).order_by(CrawlTask.created_at.desc()).first()
    recent_tasks = CrawlTask.query.filter_by(product_id=product.id).order_by(CrawlTask.created_at.desc()).limit(5).all()

    comment_count = 0
    last_comment_date = None
    stats = db.session.query(
        db.func.count(Comment.id),
        db.func.max(Comment.created_at),
    ).filter(Comment.product_id == product.id).first()
    if stats:
        comment_count = stats[0] or 0
        last_comment_date = stats[1].isoformat() if stats[1] else None

    # Comment growth rate (last 14 days vs previous 14 days)
    now = utcnow()
    current_period = Comment.query.filter(
        Comment.product_id == product.id,
        Comment.created_at >= now - timedelta(days=14),
    ).count()
    prev_period = Comment.query.filter(
        Comment.product_id == product.id,
        Comment.created_at >= now - timedelta(days=28),
        Comment.created_at < now - timedelta(days=14),
    ).count()
    growth_rate = None
    if prev_period > 0:
        growth_rate = round((current_period - prev_period) / prev_period * 100, 1)

    # Latest price from ProductPrice
    latest_price = None
    latest_price_at = None
    latest_price_record = product.prices.first()
    if latest_price_record:
        latest_price = latest_price_record.price
        latest_price_at = latest_price_record.recorded_at.isoformat() if latest_price_record.recorded_at else None

    return {
        "comment_count": comment_count,
        "last_comment_date": last_comment_date,
        "comment_growth_14d": growth_rate,
        "comment_growth_trend": "up" if growth_rate and growth_rate > 10 else ("down" if growth_rate and growth_rate < -10 else "stable"),
        "latest_price": latest_price,
        "latest_price_at": latest_price_at,
        "crawl_task": crawl_task.to_dict() if crawl_task else None,
        "recent_tasks": [t.to_dict() for t in recent_tasks] if recent_tasks else [],
    }


def _product_with_monitoring(product):
    """Return product dict with monitoring info merged in."""
    d = product.to_dict()
    d["monitoring"] = _monitoring_info(product)
    return d
