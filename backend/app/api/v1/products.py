from flask import request
from app.extensions import db
from app.models.product import Product
from app.models.crawl_task import CrawlTask
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.utils.pagination import paginate_query
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


@api_bp.route("/products/<int:product_id>/monitoring", methods=["GET"])
@require_auth
def get_product_monitoring(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    return success(_monitoring_info(product))


def _monitoring_info(product):
    """Return crawl task monitoring info for a product."""
    crawl_task = CrawlTask.query.filter_by(product_id=product.id).order_by(CrawlTask.created_at.desc()).first()
    recent_tasks = CrawlTask.query.filter_by(product_id=product.id).order_by(CrawlTask.created_at.desc()).limit(5).all()

    comment_count = 0
    last_comment_date = None
    from app.models.comment import Comment
    stats = db.session.query(
        db.func.count(Comment.id),
        db.func.max(Comment.created_at),
    ).filter(Comment.product_id == product.id).first()
    if stats:
        comment_count = stats[0] or 0
        last_comment_date = stats[1].isoformat() if stats[1] else None

    return {
        "comment_count": comment_count,
        "last_comment_date": last_comment_date,
        "crawl_task": crawl_task.to_dict() if crawl_task else None,
        "recent_tasks": [t.to_dict() for t in recent_tasks] if recent_tasks else [],
    }


def _product_with_monitoring(product):
    """Return product dict with monitoring info merged in."""
    d = product.to_dict()
    d["monitoring"] = _monitoring_info(product)
    return d
