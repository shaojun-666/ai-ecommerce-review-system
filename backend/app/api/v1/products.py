from flask import request
from app.extensions import db
from app.models.product import Product
from app.utils.auth import require_auth, require_admin
from app.utils.response import success, fail
from app.utils.pagination import paginate_query
from app.api.v1 import api_bp


@api_bp.route("/products", methods=["GET"])
@require_auth
def list_products(current_user):
    q = Product.query.order_by(Product.created_at.desc())
    if current_user.role != "admin":
        q = q.filter(db.or_(Product.user_id == current_user.id, Product.user_id.is_(None)))

    items, total, page, per_page = paginate_query(q)
    return success(
        [p.to_dict() for p in items],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@api_bp.route("/products/<int:product_id>", methods=["GET"])
@require_auth
def get_product(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    return success(product.to_dict())


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
    return success(product.to_dict())


@api_bp.route("/products/<int:product_id>", methods=["DELETE"])
@require_auth
@require_admin
def delete_product(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    db.session.delete(product)
    db.session.commit()
    return success(message="Product deleted")
