"""Tests for ReviewPreprocessor."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
from src.data_processing.preprocessor import ReviewPreprocessor


class TestReviewPreprocessor:
    def setup_method(self):
        self.preprocessor = ReviewPreprocessor()

    def test_clean_text(self):
        assert self.preprocessor.clean_text(" 质量非常好  ") == "质量非常好"
        assert self.preprocessor.clean_text("https://example.com 不错") == "不错"
        assert self.preprocessor.clean_text("") == ""

    def test_preprocess_dataframe(self):
        df = pd.DataFrame({
            "content": ["产品质量很好很满意", "一般般吧不算好", "这个产品不太好用"],
            "label": [2, 1, 0],
        })
        result = self.preprocessor.preprocess_dataframe(df, text_column="content", label_column="label", min_length=4)
        assert len(result) == 3
        assert "content" in result.columns

    def test_preprocess_dataframe_remove_short(self):
        df = pd.DataFrame({
            "content": ["好", "质量非常好", "不错的产品"],
            "label": [1, 2, 1],
        })
        result = self.preprocessor.preprocess_dataframe(df, label_column="label", min_length=3)
        assert len(result) == 2  # "好" should be removed

    def test_train_val_split(self):
        pytest.importorskip("sklearn")
        df = pd.DataFrame({"content": [f"review {i}" for i in range(100)], "label": [i % 3 for i in range(100)]})
        train, val = self.preprocessor.train_val_split(df, val_ratio=0.2, random_state=42)
        assert len(train) == 80
        assert len(val) == 20
