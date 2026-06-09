"""Tests for ModelEvaluator."""
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
pytest.importorskip("sklearn")

from src.evaluation.evaluate import ModelEvaluator


class TestModelEvaluator:
    def setup_method(self):
        self.evaluator = ModelEvaluator()

    def test_evaluate_perfect(self):
        result = self.evaluator.evaluate([0, 1, 2], [0, 1, 2])
        assert result["accuracy"] == 1.0
        assert result["f1_weighted"] == 1.0
        assert "per_class" in result
        assert "confusion_matrix" in result

    def test_evaluate_partial(self):
        result = self.evaluator.evaluate([0, 0, 1, 1, 2, 2], [0, 1, 0, 1, 2, 2])
        assert result["accuracy"] < 1.0
        assert len(result["confusion_matrix"]) == 3

    def test_evaluate_with_labels(self):
        labels = ["negative", "neutral", "positive"]
        result = self.evaluator.evaluate([0, 1, 2], [0, 1, 2], labels=labels)
        assert result["per_class"]["negative"]["f1"] == 1.0

    def test_evaluate_empty(self):
        result = self.evaluator.evaluate([], [])
        assert result["accuracy"] == 1.0

    def test_compare_models(self):
        bert = {"accuracy": 0.85, "f1_weighted": 0.84}
        llm = {"accuracy": 0.90, "f1_weighted": 0.89}
        comparison = self.evaluator.compare_models(bert, llm)
        assert comparison["delta"]["accuracy"] == 0.05
        assert comparison["delta"]["f1"] == 0.05

    def test_compare_models_output_file(self):
        bert = {"accuracy": 0.85, "f1_weighted": 0.84}
        llm = {"accuracy": 0.90, "f1_weighted": 0.89}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        self.evaluator.compare_models(bert, llm, output_path=path)
        with open(path) as f:
            data = json.load(f)
        assert data["bert"]["accuracy"] == 0.85
        os.unlink(path)
