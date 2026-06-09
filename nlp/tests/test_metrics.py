"""Tests for evaluation metrics."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
pytest.importorskip("sklearn")

from src.evaluation.metrics import classification_metrics, binary_auc


class TestClassificationMetrics:
    def test_perfect_prediction(self):
        y_true = [0, 1, 2, 0, 1, 2]
        y_pred = [0, 1, 2, 0, 1, 2]
        metrics = classification_metrics(y_true, y_pred)
        assert metrics["accuracy"] == 1.0
        assert metrics["f1"] == 1.0

    def test_partial_prediction(self):
        y_true = [0, 0, 0, 1, 1, 1]
        y_pred = [0, 0, 1, 1, 1, 0]
        metrics = classification_metrics(y_true, y_pred)
        assert 0.5 <= metrics["accuracy"] <= 0.8
        assert 0.5 <= metrics["f1"] <= 0.8


class TestBinaryAUC:
    def test_perfect_auc(self):
        y_true = [0, 0, 1, 1]
        y_scores = [0.1, 0.2, 0.9, 0.8]
        auc = binary_auc(y_true, y_scores)
        assert auc >= 0.9

    def test_random_auc(self):
        y_true = [0, 1] * 50
        y_scores = [i / 100 for i in range(100)]
        auc = binary_auc(y_true, y_scores)
        assert 0.4 <= auc <= 0.6
