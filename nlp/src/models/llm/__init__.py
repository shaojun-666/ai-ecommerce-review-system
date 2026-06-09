"""Qwen2.5-1.5B distilled LLM integration for review analysis.

This module provides integration with Qwen2.5-1.5B-Instruct for zero-shot
review analysis. The LLM approach handles sentiment analysis, aspect extraction,
keyword identification, and fake review detection in a single pass.

Usage:
    >>> from nlp.src.models.llm import LLMAnalyzer
    >>> analyzer = LLMAnalyzer()
    >>> result = analyzer.analyze("这个产品质量很好，续航不错")
    >>> print(result["sentiment"])

Requirements:
    - transformers >= 4.37
    - torch >= 2.1
    - 4-bit quantization: bitsandbytes, accelerate
    - Model weights: Qwen/Qwen2.5-1.5B-Instruct (~3GB 4bit)
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """Qwen2.5-1.5B LLM for zero-shot review analysis."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
        model_path: Optional[str] = None,
        use_4bit: bool = True,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.model_path = model_path
        self.use_4bit = use_4bit
        self.device = device or "cpu"
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """Lazy-load the model (heavy operation)."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch

            path = self.model_path or self.model_name

            quantization_config = None
            if self.use_4bit and torch.cuda.is_available():
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )

            self._tokenizer = AutoTokenizer.from_pretrained(path)
            self._model = AutoModelForCausalLM.from_pretrained(
                path,
                quantization_config=quantization_config,
                device_map="auto" if torch.cuda.is_available() else None,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
            self._model.eval()
            logger.info("Qwen2.5-1.5B model loaded from %s", path)
        except ImportError as e:
            raise RuntimeError(
                "Failed to load Qwen2 model. Ensure transformers>=4.37, torch>=2.1, "
                f"bitsandbytes are installed. Error: {e}"
            )

    def analyze(self, text: str) -> dict:
        if self._model is None:
            self._load_model()

        prompt = (
            "分析以下电商评论，返回JSON格式结果包含："
            "sentiment(positive/negative/neutral), "
            "aspects(涉及的方面如quality/logistics/service/price), "
            "keywords(关键词列表), summary(一句话总结), "
            f"is_fake(是否为虚假评论true/false)。\n评论：{text}"
        )

        import torch
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=False,
            )

        response = self._tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
        )

        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            result = json.loads(json_match.group()) if json_match else {}
        except (json.JSONDecodeError, AttributeError):
            result = {}

        sentiment = result.get("sentiment", "neutral")
        keywords = result.get("keywords", [])
        is_fake = result.get("is_fake", False)
        has_aspects = bool(result.get("aspects"))

        confidence = 0.5
        if sentiment in ("positive", "negative", "neutral"):
            confidence += 0.25
        if keywords and len(keywords) >= 2:
            confidence += 0.1
        if has_aspects:
            confidence += 0.1
        if is_fake is not None:
            confidence += 0.05

        return {
            "sentiment": sentiment,
            "sentiment_score": round(min(confidence, 0.95), 4),
            "aspects": result.get("aspects", []),
            "keywords": keywords,
            "summary": result.get("summary", response.strip()[:200]),
            "fake_score": 0.8 if is_fake else 0.1,
            "model_version": "qwen2.5-1.5b",
        }

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        return [self.analyze(t) for t in texts]


def create_analyzer(model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", **kwargs) -> LLMAnalyzer:
    return LLMAnalyzer(model_name=model_name, **kwargs)
