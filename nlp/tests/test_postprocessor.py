"""Tests for inference postprocessor."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.inference.postprocessor import format_sentiment_result, format_batch_results, merge_with_heuristic


class TestFormatSentimentResult:
    def test_format_full(self):
        raw = {
            "sentiment": "positive",
            "sentiment_score": 0.9567,
            "aspects": {"quality": 0.9},
            "keywords": ["续航", "质量"],
            "summary": "产品很好",
            "fake_score": 0.1234,
            "model_version": "bert-test",
        }
        result = format_sentiment_result(raw)
        assert result["sentiment"] == "positive"
        assert result["sentiment_score"] == 0.9567
        assert result["fake_score"] == 0.1234

    def test_format_minimal(self):
        result = format_sentiment_result({})
        assert result["sentiment"] == "neutral"
        assert result["sentiment_score"] == 0
        assert result["model_version"] == "unknown"


class TestFormatBatchResults:
    def test_batch(self):
        results = [
            {"sentiment": "positive", "sentiment_score": 0.9},
            {"sentiment": "negative", "sentiment_score": 0.8},
        ]
        formatted = format_batch_results(results)
        assert len(formatted) == 2
        assert formatted[0]["sentiment"] == "positive"
        assert formatted[1]["sentiment"] == "negative"


class TestMergeWithHeuristic:
    def test_short_text_increases_fake_score(self):
        nlp_result = {"fake_score": 0.0, "sentiment": "positive"}
        result = merge_with_heuristic(nlp_result, "好")
        assert result["fake_score"] > 0.2

    def test_excessive_punctuation(self):
        nlp_result = {"fake_score": 0.0, "sentiment": "positive"}
        result = merge_with_heuristic(nlp_result, "太好了太好了太好了太好了太好了太好了！！！！！！太好了！！")
        assert result["fake_score"] > 0.1

    def test_repeated_chars(self):
        nlp_result = {"fake_score": 0.0, "sentiment": "positive"}
        result = merge_with_heuristic(nlp_result, "好好好好好好")
        assert result["fake_score"] > 0.1

    def test_score_capped(self):
        nlp_result = {"fake_score": 0.95, "sentiment": "positive"}
        result = merge_with_heuristic(nlp_result, "好")
        assert result["fake_score"] <= 1.0
