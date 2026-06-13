"""Tests for category classifier service."""
import pytest
from app.services.category_classifier import classify_product_name, auto_categorize_product


class TestClassifyProductName:
    def test_phone_keyword(self):
        assert classify_product_name("华为Mate60 Pro手机") == "phone"

    def test_laptop_keyword(self):
        assert classify_product_name("联想拯救者Y9000P 笔记本") == "laptop"

    def test_clothing_keyword(self):
        assert classify_product_name("夏季纯棉T恤男装") == "clothing"

    def test_food_keyword(self):
        assert classify_product_name("进口坚果零食礼盒装") == "food"

    def test_skincare_keyword(self):
        assert classify_product_name("兰蔻精华面霜保湿") == "skincare"

    def test_sports_keyword(self):
        assert classify_product_name("瑜伽垫健身器材套装") == "sports"

    def test_home_appliance_keyword(self):
        assert classify_product_name("美的智能电饭煲4L") == "home-appliance"

    def test_books_keyword(self):
        assert classify_product_name("三体全集科幻小说") == "books"

    def test_uncategorized(self):
        assert classify_product_name("XYZ-123-通用商品") == "uncategorized"

    def test_empty_name(self):
        assert classify_product_name("") == "uncategorized"
        assert classify_product_name(None) == "uncategorized"

    def test_case_insensitive(self):
        assert classify_product_name("iPhone 15 Pro Max") == "phone"

    def test_pet_keyword(self):
        assert classify_product_name("皇家猫粮幼猫专用") == "pet"

    def test_auto_keyword(self):
        assert classify_product_name("汽车坐垫冬季") == "auto"

    def test_higher_priority_wins(self):
        """家电(100) should beat kitchen(90)."""
        assert classify_product_name("美的微波炉家用") == "home-appliance"

    def test_baby_product(self):
        assert classify_product_name("婴儿奶粉1段") == "baby"

    def test_multiple_keywords_uses_highest_priority(self):
        assert classify_product_name("运动蓝牙耳机无线") == "headphones"
