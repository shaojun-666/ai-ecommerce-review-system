"""User management API (admin + self-service)."""
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.api.v1 import api_bp
from app.utils.auth import require_auth, require_admin
from app.extensions import db
from app.models.user import User


@api_bp.route("/users/me", methods=["GET"])
@require_auth
def get_my_profile(current_user):
    return jsonify({"user": current_user.to_dict()})


@api_bp.route("/users/me", methods=["PUT"])
@require_auth
def update_my_profile(current_user):
    data = request.get_json() or {}
    if "username" in data:
        existing = User.query.filter(
            User.username == data["username"],
            User.id != current_user.id,
        ).first()
        if existing:
            return jsonify({"error": "Username already exists"}), 409
        current_user.username = data["username"]
    if "email" in data:
        existing = User.query.filter(
            User.email == data["email"],
            User.id != current_user.id,
        ).first()
        if existing:
            return jsonify({"error": "Email already exists"}), 409
        current_user.email = data["email"]
    db.session.commit()
    return jsonify({"message": "Profile updated", "user": current_user.to_dict()})


@api_bp.route("/users/me/password", methods=["PUT"])
@require_auth
def change_my_password(current_user):
    data = request.get_json() or {}
    old_password = data.get("oldPassword")
    new_password = data.get("newPassword")
    if not old_password or not new_password:
        return jsonify({"error": "oldPassword and newPassword required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not check_password_hash(current_user.password_hash, old_password):
        return jsonify({"error": "Current password is incorrect"}), 403
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Password updated"})


@api_bp.route("/users/me/preferences", methods=["GET"])
@require_auth
def get_my_preferences(current_user):
    return jsonify({"preferences": current_user.preferences or {}})


@api_bp.route("/users/me/preferences", methods=["PUT"])
@require_auth
def update_my_preferences(current_user):
    data = request.get_json() or {}
    # Merge with existing preferences
    prefs = dict(current_user.preferences or {})
    prefs.update(data)
    current_user.preferences = prefs
    db.session.commit()
    return jsonify({"message": "Preferences updated", "preferences": prefs})


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
