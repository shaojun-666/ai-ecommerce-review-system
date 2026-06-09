"""Text cleaning and normalization for Chinese reviews."""
import re


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("…", "...")
    text = re.sub(r"(.)\1{4,}", r"\1\1\1\1", text)
    return text.strip()


def normalize_rating(rating) -> int:
    try:
        r = int(float(rating))
        return max(1, min(5, r))
    except (ValueError, TypeError):
        return 3


def is_valid_review(text: str, min_length: int = 5, max_length: int = 10000) -> bool:
    if not text or len(text) < min_length:
        return False
    if len(text) > max_length:
        return False
    if re.match(r"^[\s!！?？.。，,]+$", text):
        return False
    return True


def detect_language(text: str) -> str:
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    if chinese_chars > len(text) * 0.3:
        return "zh"
    return "other"
