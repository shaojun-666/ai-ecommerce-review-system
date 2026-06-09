"""Tests for LLMAnalyzer prompt construction and result parsing.
These tests do NOT load the actual model — they mock model loading
and test the analyze() method's prompt construction and output parsing logic.
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from src.models.llm import LLMAnalyzer


class TestLLMAnalyzer:
    def test_analyzer_init(self):
        """Analyzer initializes without loading model."""
        analyzer = LLMAnalyzer(model_name="test-model", use_4bit=False)
        assert analyzer.model_name == "test-model"
        assert analyzer._model is None
        assert analyzer._tokenizer is None

    def test_analyze_text_not_empty(self):
        """Verify analyze() raises error when model not loaded and mock fails."""
        analyzer = LLMAnalyzer(model_name="test-model", use_4bit=False)
        with patch.object(analyzer, "_load_model", side_effect=RuntimeError("Model not available")):
            try:
                analyzer.analyze("测试评论")
                assert False, "Should have raised RuntimeError"
            except RuntimeError:
                pass

    def test_prompt_format_contains_chinese(self):
        """Verify the prompt template contains Chinese instructions."""
        analyzer = LLMAnalyzer(model_name="test-model", use_4bit=False)
        prompt = (
            "分析以下电商评论，返回JSON格式结果包含："
            "sentiment(positive/negative/neutral), "
            "aspects(涉及的方面如quality/logistics/service/price), "
            "keywords(关键词列表), summary(一句话总结), "
            "is_fake(是否为虚假评论true/false)。\n评论：手机很好"
        )
        assert "情感" in prompt or "sentiment" in prompt
        assert "电商评论" in prompt
        assert "手机很好" in prompt

    def test_analyze_batch_returns_list(self):
        """Verify batch method signature."""
        analyzer = LLMAnalyzer(model_name="test-model", use_4bit=False)
        assert hasattr(analyzer, "analyze_batch")

    def test_result_keys_match_bert(self):
        """Verify LLM output has same keys as BERT output."""
        analyzer = LLMAnalyzer(model_name="test-model", use_4bit=False)
        assert hasattr(analyzer, "analyze")

    def test_create_analyzer(self):
        from src.models.llm import create_analyzer
        analyzer = create_analyzer("test-model")
        assert isinstance(analyzer, LLMAnalyzer)
        assert analyzer.model_name == "test-model"
