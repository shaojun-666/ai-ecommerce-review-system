"""Tests for ErrorAnalyzer."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.error_analysis import ErrorAnalyzer


class TestErrorAnalyzer:
    def setup_method(self):
        self.analyzer = ErrorAnalyzer()

    def test_analyze_bad_cases(self):
        texts = ["产品好", "质量差", "一般"]
        y_true = [2, 0, 1]
        y_pred = [2, 1, 1]  # second is wrong (0→1)
        cases = self.analyzer.analyze_bad_cases(texts, y_true, y_pred)
        assert len(cases) == 1
        assert cases[0]["true_label"] == "negative"
        assert cases[0]["pred_label"] == "neutral"

    def test_no_bad_cases(self):
        texts = ["好", "差"]
        cases = self.analyzer.analyze_bad_cases(texts, [2, 0], [2, 0])
        assert len(cases) == 0

    def test_with_scores(self):
        texts = ["产品很好"]
        y_true = [2]
        y_pred = [0]
        scores = [0.95]
        cases = self.analyzer.analyze_bad_cases(texts, y_true, y_pred, scores)
        assert cases[0]["confidence"] == 0.95

    def test_summarize_errors(self):
        cases = [
            {"true_label": "negative", "pred_label": "positive", "confidence": 0.95},
            {"true_label": "negative", "pred_label": "neutral", "confidence": 0.85},
        ]
        summary = self.analyzer.summarize_errors(cases)
        assert summary["total"] == 2
        assert "negative→positive" in summary["confusion_summary"]
        assert summary["high_confidence_errors"] == 1  # only 0.95

    def test_summarize_empty(self):
        summary = self.analyzer.summarize_errors([])
        assert summary["total"] == 0
