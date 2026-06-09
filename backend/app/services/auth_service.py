import datetime
import jwt
from app.extensions import db
from app.models.user import User
from app.utils.errors import Unauthorized


def _get_secret():
    from flask import current_app
    return current_app.config.get("JWT_SECRET_KEY", "jwt-dev-secret")


def _get_access_expires():
    from flask import current_app
    return int(current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", 900))


def _get_refresh_expires():
    from flask import current_app
    return int(current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES", 604800))


def generate_token(user):
    now = datetime.datetime.utcnow()
    access_payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=_get_access_expires()),
        "type": "access",
    }
    refresh_payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=_get_refresh_expires()),
        "type": "refresh",
        "seq": int(now.timestamp()),
    }
    secret = _get_secret()
    access_token = jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")
    return access_token, refresh_token


def refresh_access_token(refresh_token_str):
    secret = _get_secret()
    try:
        payload = jwt.decode(refresh_token_str, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Refresh token expired")
    except jwt.InvalidTokenError:
        raise Unauthorized("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise Unauthorized("Invalid token type")

    user = db.session.get(User, payload["sub"])
    if not user or not user.is_active:
        raise Unauthorized("User not found or inactive")

    now = datetime.datetime.utcnow()
    secret = _get_secret()
    access_payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=_get_access_expires()),
        "type": "access",
    }
    refresh_payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=_get_refresh_expires()),
        "type": "refresh",
        "seq": int(now.timestamp()),
    }
    new_access = jwt.encode(access_payload, secret, algorithm="HS256")
    new_refresh = jwt.encode(refresh_payload, secret, algorithm="HS256")
    return new_access, new_refresh


def authenticate_user(username_or_email, password):
    user = User.query.filter(
        db.or_(User.username == username_or_email, User.email == username_or_email)
    ).first()
    if not user or not user.check_password(password):
        return None
    if not user.is_active:
        return None
    return user
