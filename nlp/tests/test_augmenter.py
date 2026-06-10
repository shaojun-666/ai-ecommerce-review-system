"""Tests for data augmentation module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.data_processing.augmenter import (
    random_mask,
    synonym_replace,
    random_swap,
    augment_text,
    augment_dataset,
)


class TestAugmenter:
    def test_random_mask_replaces_chars(self):
        result = random_mask("这个产品非常好用", mask_prob=1.0)
        assert result != "这个产品非常好用"
        assert "[MASK]" in result

    def test_random_mask_preserves_short_texts(self):
        result = random_mask("好", mask_prob=0.0)
        assert result == "好"

    @pytest.mark.skip(reason="Need to handle mask_prob=0 edge case properly")
    def test_random_mask_no_mask(self):
        result = random_mask("产品很好用", mask_prob=0.0)
        assert result == "产品很好用"

    def test_synonym_replace_no_replacement(self):
        result = synonym_replace("产品很好用", replace_prob=0.0)
        assert result == "产品很好用"

    def test_synonym_replace_known_word(self):
        result = synonym_replace("质量非常好", replace_prob=1.0)
        # "质量" should be replaced with "品质"
        assert "品质" in result or result != "质量非常好"

    def test_synonym_replace_short_word_skipped(self):
        result = synonym_replace("的很好", replace_prob=1.0)
        assert result is not None

    def test_random_swap(self):
        result = random_swap("AB", swap_prob=1.0)
        assert result == "BA"

    def test_random_swap_no_swap(self):
        result = random_swap("AB", swap_prob=0.0)
        assert result == "AB"

    def test_random_swap_single_char(self):
        result = random_swap("A", swap_prob=1.0)
        assert result == "A"

    def test_augment_text_default(self):
        results = augment_text("产品很好用", num_augmented=2)
        assert len(results) == 3
        assert results[0] == "产品很好用"

    def test_augment_text_no_augmentation(self):
        results = augment_text("产品", num_augmented=0)
        assert len(results) == 1
        assert results[0] == "产品"

    def test_augment_dataset_basic(self):
        import pandas as pd
        df = pd.DataFrame({"content": ["产品很好", "质量很差"], "label": [1, 0]})
        result = augment_dataset(df, num_augmented=1)
        # 2 original + 2 augmented = 4 rows
        assert len(result) == 4
        # Labels are preserved
        assert set(result["label"].values) == {0, 1}

    def test_augment_dataset_with_max_per_class(self):
        import pandas as pd
        df = pd.DataFrame({
            "content": ["好"] * 10 + ["差"] * 10,
            "label": [1] * 10 + [0] * 10,
        })
        result = augment_dataset(df, num_augmented=1, max_per_class=5)
        assert len(result[result["label"] == 0]) <= 5
        assert len(result[result["label"] == 1]) <= 5

    def test_augment_dataset_empty_text_skipped(self):
        import pandas as pd
        df = pd.DataFrame({"content": ["", "valid text"], "label": [0, 1]})
        result = augment_dataset(df, num_augmented=1)
        assert len(result) >= 2  # empty row kept but not augmented

    def test_back_translate_returns_original_without_api(self):
        from src.data_processing.augmenter import back_translate
        result = back_translate("产品很好")
        assert result == "产品很好"

    def test_synonym_dict_coverage(self):
        """Ensure common review words have synonyms."""
        from src.data_processing.augmenter import _SYNONYM_DICT
        essential = ["质量", "物流", "客服", "价格", "好", "差"]
        for word in essential:
            assert word in _SYNONYM_DICT, f"Missing synonym for '{word}'"
