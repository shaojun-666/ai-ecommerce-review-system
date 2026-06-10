"""Tests for confusion matrix analysis utilities."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from src.evaluation.confusion import (
    compute_confusion_matrix,
    confusion_to_dict,
    find_confused_pairs,
)


class TestConfusionMatrix:
    def test_compute_basic(self):
        cm = compute_confusion_matrix([0, 1, 2], [0, 1, 2])
        assert cm.shape == (3, 3)
        assert cm[0][0] == 1
        assert cm[1][1] == 1
        assert cm[2][2] == 1

    def test_compute_with_errors(self):
        y_true = [0, 0, 1, 1, 2, 2]
        y_pred = [0, 1, 0, 1, 2, 2]
        cm = compute_confusion_matrix(y_true, y_pred)
        assert cm[0][0] == 1  # one correct negative
        assert cm[0][1] == 1  # one negative predicted as neutral
        assert cm[1][0] == 1  # one neutral predicted as negative
        assert cm[1][1] == 1  # one correct neutral
        assert cm[2][2] == 2  # both positive correct

    def test_compute_with_labels(self):
        cm = compute_confusion_matrix([0, 1, 2], [0, 1, 2], labels=[0, 1, 2])
        assert cm[0][0] == 1

    def test_confusion_to_dict_default_labels(self):
        cm = compute_confusion_matrix([0, 1, 2], [0, 1, 2])
        result = confusion_to_dict(cm)
        assert result["labels"] == ["negative", "neutral", "positive"]
        assert "negative_as_negative" in result
        assert result["negative_as_negative"]["count"] == 1

    def test_confusion_to_dict_percentages(self):
        y_true = [0, 0, 0]
        y_pred = [0, 1, 2]
        cm = compute_confusion_matrix(y_true, y_pred)
        result = confusion_to_dict(cm)
        # negative: 1 correct, 2 wrong → 33.3% correct
        assert result["negative_as_negative"]["percentage"] == pytest.approx(33.3, rel=0.1)

    def test_confusion_to_dict_custom_labels(self):
        cm = compute_confusion_matrix([0, 1], [0, 1])
        result = confusion_to_dict(cm, labels=["neg", "pos"])
        assert result["labels"] == ["neg", "pos"]

    def test_find_confused_pairs(self):
        y_true = [0, 0, 1, 1, 2, 2]
        y_pred = [1, 1, 0, 0, 2, 2]
        cm = compute_confusion_matrix(y_true, y_pred)
        pairs = find_confused_pairs(cm)
        assert len(pairs) == 2
        # Both pairs have count 2, order may vary
        counts = {p["true"]: p["count"] for p in pairs}
        assert list(counts.values()) == [2, 2]

    def test_find_confused_pairs_empty(self):
        cm = compute_confusion_matrix([0, 1, 2], [0, 1, 2])
        pairs = find_confused_pairs(cm)
        assert pairs == []

    def test_find_confused_pairs_custom_labels(self):
        y_true = [0, 0, 1]
        y_pred = [1, 1, 0]
        cm = compute_confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
        pairs = find_confused_pairs(cm, labels=["neg", "neu", "pos"])
        assert len(pairs) > 0
        assert pairs[0]["true"] in ("neg", "neu", "pos")
        assert pairs[0]["predicted"] in ("neg", "neu", "pos")

    def test_empty_input(self):
        with pytest.raises(ValueError, match="empty"):
            compute_confusion_matrix([], [])

    def test_single_class(self):
        cm = compute_confusion_matrix([0, 0, 0], [0, 0, 0], labels=[0, 1, 2])
        result = confusion_to_dict(cm)
        assert result["labels"] == ["negative", "neutral", "positive"]
        assert result["matrix"][0][0] == 3
