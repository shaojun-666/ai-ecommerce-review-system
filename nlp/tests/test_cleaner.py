"""Tests for text cleaning and normalization."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: F401

from src.data_processing.cleaner import clean_text, normalize_rating, is_valid_review, detect_language


class TestCleanText:
    def test_remove_urls(self):
        assert clean_text("看看这个 https://item.jd.com/123.html 不错") == "看看这个不错"

    def test_remove_html_tags(self):
        assert clean_text("<p>质量很好</p>") == "质量很好"

    def test_collapse_whitespace(self):
        assert clean_text("质量  非常  好") == "质量非常好"

    def test_repeated_chars(self):
        result = clean_text("好好好好好好")
        assert len(result) <= 4

    def test_empty_text(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_trim_whitespace(self):
        assert clean_text("  质量不错  ") == "质量不错"


class TestNormalizeRating:
    def test_valid_ratings(self):
        assert normalize_rating("5") == 5
        assert normalize_rating(3) == 3
        assert normalize_rating("1") == 1

    def test_clamp_ratings(self):
        assert normalize_rating(0) == 1
        assert normalize_rating(6) == 5

    def test_float_ratings(self):
        assert normalize_rating(4.7) == 5
        assert normalize_rating(3.2) == 3

    def test_invalid_ratings(self):
        assert normalize_rating("abc") == 3
        assert normalize_rating(None) == 3


class TestIsValidReview:
    def test_valid_text(self):
        assert is_valid_review("这个产品质量很好，非常满意") is True

    def test_too_short(self):
        assert is_valid_review("好") is False
        assert is_valid_review("") is False

    def test_too_long(self):
        assert is_valid_review("a" * 10001) is False

    def test_only_punctuation(self):
        assert is_valid_review("！！！！！") is False

    def test_min_length_boundary(self):
        assert is_valid_review("质量很好", min_length=4) is True


class TestDetectLanguage:
    def test_chinese_text(self):
        assert detect_language("这个产品质量很好") == "zh"

    def test_english_text(self):
        assert detect_language("this is a good product") == "other"

    def test_mixed_text(self):
        # "质量很好" is 4 of ~17 chars = ~23% < 30%, so detected as "other"
        assert detect_language("质量很好, very good") == "other"
        # With more Chinese chars the proportion increases
        assert detect_language("这个产品的质量非常好，我很喜欢 it's good") == "zh"

    def test_empty_text(self):
        assert detect_language("") == "other"
