"""Product tag CRUD API."""
from flask import request
from app.extensions import db
from app.models.product_tag import ProductTag, product_tag_map
from app.models.product import Product
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.api.v1 import api_bp


@api_bp.route("/tags", methods=["GET"])
@require_auth
def list_tags(current_user):
    tags = ProductTag.query.order_by(ProductTag.name).all()
    return success([t.to_dict() for t in tags])


@api_bp.route("/tags", methods=["POST"])
@require_auth
def create_tag(current_user):
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("Tag name is required", 422)
    if ProductTag.query.filter_by(name=name).first():
        return fail("Tag already exists", 409)
    tag = ProductTag(
        name=name,
        color=data.get("color", "#409eff"),
        user_id=current_user.id,
    )
    db.session.add(tag)
    db.session.commit()
    return success(tag.to_dict(), message="Tag created", code=201)


@api_bp.route("/tags/<int:tag_id>", methods=["PUT"])
@require_auth
def update_tag(current_user, tag_id):
    tag = db.session.get(ProductTag, tag_id)
    if not tag:
        return fail("Tag not found", 404)
    data = request.get_json(force=True)
    if "name" in data:
        name = data["name"].strip()
        if not name:
            return fail("Tag name cannot be empty", 422)
        existing = ProductTag.query.filter_by(name=name).first()
        if existing and existing.id != tag_id:
            return fail("Tag name already exists", 409)
        tag.name = name
    if "color" in data:
        tag.color = data["color"]
    db.session.commit()
    return success(tag.to_dict())


@api_bp.route("/tags/<int:tag_id>", methods=["DELETE"])
@require_auth
def delete_tag(current_user, tag_id):
    tag = db.session.get(ProductTag, tag_id)
    if not tag:
        return fail("Tag not found", 404)
    db.session.delete(tag)
    db.session.commit()
    return success(message="Tag deleted")


@api_bp.route("/products/<int:product_id>/tags", methods=["PUT"])
@require_auth
def set_product_tags(current_user, product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return fail("Product not found", 404)
    data = request.get_json(force=True)
    tag_ids = data.get("tag_ids", [])
    tags = ProductTag.query.filter(ProductTag.id.in_(tag_ids)).all()
    product.tags = tags
    db.session.commit()
    return success(product.to_dict())
