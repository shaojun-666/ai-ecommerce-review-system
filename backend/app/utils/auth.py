"""JWT authentication utilities."""
import datetime
from functools import wraps
from flask import request, jsonify, current_app
import jwt
from app.extensions import db
from app.models.user import User


def generate_token(user: User) -> tuple[str, str]:
    """Generate access + refresh token pair."""
    now = datetime.datetime.utcnow()
    access_payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]),
        "type": "access",
    }
    refresh_payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]),
        "type": "refresh",
    }
    secret = current_app.config["JWT_SECRET_KEY"]
    access_token = jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")
    return access_token, refresh_token


def refresh_access_token(refresh_token: str) -> dict | None:
    """Exchange a refresh token for a new access token."""
    try:
        secret = current_app.config["JWT_SECRET_KEY"]
        payload = jwt.decode(refresh_token, secret, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return None
        user = db.session.get(User, payload["sub"])
        if not user or not user.is_active:
            return None
        access_token, _ = generate_token(user)
        return {"access_token": access_token}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """Decorator that requires a valid JWT access token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            secret = current_app.config["JWT_SECRET_KEY"]
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            if payload.get("type") != "access":
                return jsonify({"error": "Invalid token type"}), 401
            user = db.session.get(User, payload["sub"])
            if not user or not user.is_active:
                return jsonify({"error": "User not found or disabled"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(user, *args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator that requires admin role (must come after @require_auth)."""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(current_user, *args, **kwargs)
    return decorated
