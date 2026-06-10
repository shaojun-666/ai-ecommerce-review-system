import re


def validate_url(url: str) -> bool:
    """Basic URL validation — checks for http/https scheme."""
    if not url:
        return False
    return bool(re.match(r"^https?://", url.strip()))


def validate_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip())) if email else False


def validate_password(password):
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    return True, ""


def validate_username(username):
    if not username or len(username) < 2:
        return False, "Username must be at least 2 characters"
    if len(username) > 64:
        return False, "Username must be at most 64 characters"
    if not re.match(r"^[a-zA-Z0-9_一-龥]+$", username):
        return False, "Username can only contain letters, digits, underscores, and Chinese characters"
    return True, ""


def validate_rating(rating):
    if rating is None:
        return True, ""
    try:
        r = int(rating)
        if 1 <= r <= 5:
            return True, ""
        return False, "Rating must be between 1 and 5"
    except (ValueError, TypeError):
        return False, "Rating must be an integer"


def validate_platform(platform):
    allowed = ["京东", "淘宝", "拼多多", "天猫", "亚马逊", "其他", None, ""]
    return platform in allowed


def validate_page_params(page, per_page):
    try:
        p = int(page) if page else 1
        pp = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        return 1, 20
    if p < 1:
        p = 1
    if pp < 1:
        pp = 1
    if pp > 100:
        pp = 100
    return p, pp
