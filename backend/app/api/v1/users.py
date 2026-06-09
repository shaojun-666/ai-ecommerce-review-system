"""User management API (admin only)."""
from flask import request, jsonify
from werkzeug.security import generate_password_hash
from app.api.v1 import api_bp
from app.utils.auth import require_auth, require_admin
from app.extensions import db
from app.models.user import User


@api_bp.route("/users", methods=["GET"])
@require_auth
@require_admin
def list_users(current_user):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = User.query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@api_bp.route("/users", methods=["POST"])
@require_auth
@require_admin
def create_user(current_user):
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not all([username, email, password]):
        return jsonify({"error": "username, email, password required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=data.get("role", "user"),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 201


@api_bp.route("/users/<int:user_id>", methods=["PUT"])
@require_auth
@require_admin
def update_user(current_user, user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}

    if "username" in data:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "role" in data:
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "password" in data:
        user.password_hash = generate_password_hash(data["password"])

    db.session.commit()
    return jsonify({"user": user.to_dict()})
