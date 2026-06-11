"""Authentication API endpoints."""
from flask import request, jsonify
from app.api.v1 import api_bp
from app.utils.auth import generate_token, require_auth
from app import limiter


@api_bp.route("/auth/login", methods=["POST"])
@limiter.limit("10/minute")
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    # TODO: verify against database
    from app.models.user import User
    from werkzeug.security import check_password_hash

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403

    access_token, refresh_token = generate_token(user)
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    })


@api_bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not all([username, email, password]):
        return jsonify({"error": "Username, email, and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    from app.models.user import User
    from werkzeug.security import generate_password_hash

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    from app.extensions import db
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Registration successful"}), 201


@api_bp.route("/auth/refresh", methods=["POST"])
def refresh():
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Refresh token required"}), 400

    from app.utils.auth import refresh_access_token
    result = refresh_access_token(refresh_token)
    if result is None:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    return jsonify(result)


@api_bp.route("/auth/me", methods=["GET"])
@require_auth
def get_current_user(current_user):
    return jsonify({"user": current_user.to_dict()})
