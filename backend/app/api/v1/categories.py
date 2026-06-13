"""Category CRUD and auto-classification API."""
from flask import request
from app.extensions import db
from app.models.category import Category, product_category_map
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.api.v1 import api_bp


@api_bp.route("/categories", methods=["GET"])
@require_auth
def list_categories(current_user):
    """List all categories as a flat list or tree."""
    tree = request.args.get("tree", "0").lower() in ("1", "true", "yes")
    categories = Category.query.order_by(Category.level, Category.name).all()

    if tree:
        roots = [c for c in categories if c.parent_id is None]
        return success([c.to_dict(include_children=True) for c in roots])

    return success([c.to_dict() for c in categories])


@api_bp.route("/categories/<int:category_id>", methods=["GET"])
@require_auth
def get_category(current_user, category_id):
    category = Category.query.get(category_id)
    if not category:
        return fail("Category not found", 404)
    return success(category.to_dict(include_children=True))


@api_bp.route("/categories", methods=["POST"])
@require_auth
def create_category(current_user):
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip()
    if not name or not slug:
        return fail("Name and slug are required", 422)

    if Category.query.filter_by(slug=slug).first():
        return fail("Category slug already exists", 409)

    parent_id = data.get("parent_id")
    parent = None
    level = 0
    if parent_id:
        parent = Category.query.get(parent_id)
        if not parent:
            return fail("Parent category not found", 404)
        level = parent.level + 1

    category = Category(
        name=name,
        slug=slug,
        icon=data.get("icon", ""),
        parent_id=parent_id,
        level=level,
    )
    db.session.add(category)
    db.session.commit()
    return success(category.to_dict(), 201)


@api_bp.route("/categories/<int:category_id>", methods=["PUT"])
@require_auth
def update_category(current_user, category_id):
    category = Category.query.get(category_id)
    if not category:
        return fail("Category not found", 404)

    data = request.get_json(force=True)
    name = data.get("name")
    slug = data.get("slug")
    icon = data.get("icon")

    if name is not None:
        category.name = name.strip()
    if slug is not None:
        slug = slug.strip()
        if slug != category.slug and Category.query.filter_by(slug=slug).first():
            return fail("Category slug already exists", 409)
        category.slug = slug
    if icon is not None:
        category.icon = icon

    db.session.commit()
    return success(category.to_dict())


@api_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@require_auth
def delete_category(current_user, category_id):
    category = Category.query.get(category_id)
    if not category:
        return fail("Category not found", 404)
    if category.children:
        return fail("Cannot delete category with children", 409)

    db.session.delete(category)
    db.session.commit()
    return success({"deleted": category_id})


@api_bp.route("/products/<int:product_id>/categories", methods=["GET"])
@require_auth
def get_product_categories(current_user, product_id):
    """Get categories for a product."""
    from app.models.product import Product
    product = Product.query.get(product_id)
    if not product:
        return fail("Product not found", 404)

    cats = Category.query.join(product_category_map).filter(
        product_category_map.c.product_id == product_id
    ).all()
    return success([c.to_dict() for c in cats])


@api_bp.route("/products/<int:product_id>/categories", methods=["POST"])
@require_auth
def set_product_categories(current_user, product_id):
    """Set categories for a product (replaces all)."""
    from app.models.product import Product
    product = Product.query.get(product_id)
    if not product:
        return fail("Product not found", 404)

    data = request.get_json(force=True)
    category_ids = data.get("category_ids", [])
    if not isinstance(category_ids, list):
        return fail("category_ids must be a list", 422)

    # Remove existing
    db.session.execute(
        product_category_map.delete().where(product_category_map.c.product_id == product_id)
    )

    # Add new
    for cid in category_ids:
        if Category.query.get(cid):
            db.session.execute(
                product_category_map.insert().values(product_id=product_id, category_id=cid)
            )

    db.session.commit()
    cats = Category.query.join(product_category_map).filter(
        product_category_map.c.product_id == product_id
    ).all()
    return success([c.to_dict() for c in cats])


@api_bp.route("/categories/auto-classify", methods=["POST"])
@require_auth
def auto_classify_all(current_user):
    """Run auto-classification on all uncategorized products."""
    from app.services.category_classifier import batch_categorize_all
    stats = batch_categorize_all()
    return success(stats)
