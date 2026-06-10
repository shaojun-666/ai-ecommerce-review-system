"""Text cleaning and validation for Chinese reviews.

Mirrors nlp/src/data_processing/cleaner.py but with no external
dependencies (no torch/transformers), for use in the backend data pipeline.
"""
import re
import hashlib


def clean_text(text: str) -> str:
    """Strip URLs, HTML tags, normalize whitespace, truncate repeat chars."""
    if not text:
        return ""
    # Strip HTML first to handle URLs embedded in attributes
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://[^\s<>\"']+", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("…", "...")
    text = re.sub(r"(.)\1{4,}", r"\1\1\1\1", text)
    return text.strip()


def normalize_rating(rating) -> int:
    """Clamp rating to [1, 5], default to 3 on failure.

    Uses ``int(x + 0.5)`` instead of ``round()`` to avoid Python 3's
    banker's rounding (``round(4.5) == 4``) which is unintuitive for
    review ratings.
    """
    try:
        r = float(rating)
        return max(1, min(5, int(r + 0.5)))
    except (ValueError, TypeError):
        return 3


def is_valid_review(text: str, min_length: int = 5, max_length: int = 10000) -> bool:
    """Check if review meets length and content requirements."""
    if not text or len(text) < min_length:
        return False
    if len(text) > max_length:
        return False
    if re.match(r"^[\s!！?？.。，,]+$", text):
        return False
    return True


def detect_language(text: str) -> str:
    """Heuristic: return 'zh' if >30% of chars are Chinese, else 'other'."""
    if not text:
        return "other"
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    if chinese_chars > len(text) * 0.3:
        return "zh"
    return "other"


def content_hash(text: str) -> str:
    """SHA-256 hex digest of cleaned text for dedup."""
    return hashlib.sha256(clean_text(text).encode("utf-8")).hexdigest()
