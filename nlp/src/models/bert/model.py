"""BERT-based sentiment analysis model for inference."""
import os
import json
import logging
from typing import Optional

import torch
import numpy as np
from transformers import BertTokenizer, BertForSequenceClassification

logger = logging.getLogger(__name__)


class BERTPredictor:
    """BERT predictor for Chinese review sentiment analysis."""

    def __init__(
        self,
        model_name: str = "bert-base-chinese",
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        num_labels: int = 3,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name

        model_dir = model_path or model_name
        if os.path.exists(os.path.join(str(model_dir), "config.json")):
            logger.info("Loading model from local path: %s", model_dir)
            self.tokenizer = BertTokenizer.from_pretrained(str(model_dir))
            self.model = BertForSequenceClassification.from_pretrained(
                str(model_dir), num_labels=num_labels
            )
        else:
            logger.info("Loading model from HuggingFace: %s", model_name)
            self.tokenizer = BertTokenizer.from_pretrained(model_name)
            self.model = BertForSequenceClassification.from_pretrained(
                model_name, num_labels=num_labels
            )

        self.model.to(self.device)
        self.model.eval()
        logger.info("BERT model loaded on %s", self.device)

        # Aspect keywords (simplified aspect-based analysis)
        self.aspect_keywords = {
            "quality": ["质量", "做工", "材质", "耐用", "手感", "品质", "结实", "完好"],
            "logistics": ["物流", "快递", "送货", "配送", "发货", "速度", "包装", "运输"],
            "service": ["客服", "服务", "态度", "售后", "退换", "回复", "处理", "耐心"],
            "price": ["价格", "性价比", "划算", "便宜", "贵", "优惠", "折扣", "值"],
        }

    @torch.no_grad()
    def predict(self, text: str) -> dict:
        """Predict sentiment for a single text."""
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self.device)

        outputs = self.model(**inputs)
        logits = outputs.logits
        probabilities = torch.softmax(logits, dim=-1).cpu().numpy()[0]

        # labels: 0=negative, 1=neutral, 2=positive
        sentiment_idx = int(np.argmax(probabilities))
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        sentiment = sentiment_map[sentiment_idx]
        score = float(probabilities[sentiment_idx])

        # Aspect analysis
        aspects = self._extract_aspects(text)

        # Keyword extraction
        keywords = self._extract_keywords(text)

        # Fake review scoring (placeholder — uses simple heuristics)
        fake_score = self._compute_fake_score(text, sentiment)

        return {
            "sentiment": sentiment,
            "sentiment_score": round(score, 4),
            "aspects": aspects,
            "keywords": keywords,
            "summary": None,
            "fake_score": round(fake_score, 4),
            "model_version": f"bert-{self.model_name}",
        }

    @torch.no_grad()
    def predict_batch(self, texts: list[str]) -> list[dict]:
        """Predict sentiment for a batch of texts."""
        return [self.predict(t) for t in texts]

    def _extract_aspects(self, text: str) -> dict:
        """Simple aspect-based keyword matching."""
        scores = {}
        for aspect, keywords in self.aspect_keywords.items():
            match_count = sum(1 for kw in keywords if kw in text)
            scores[aspect] = round(min(match_count / 3.0, 1.0), 4) if match_count > 0 else 0.0
        return scores

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract key terms from text."""
        import jieba
        stop_words = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        words = jieba.lcut(text)
        filtered = [w for w in words if len(w) >= 2 and w not in stop_words]
        # Return top 5 by frequency (simplified)
        return filtered[:5]

    def _compute_fake_score(self, text: str, sentiment: str) -> float:
        """Heuristic fake review scoring."""
        score = 0.0
        # Short texts are suspicious
        if len(text) < 10:
            score += 0.3
        elif len(text) < 20:
            score += 0.15

        # All-caps or excessive punctuation
        exclamation_count = text.count("!") + text.count("！")
        if exclamation_count > 5:
            score += 0.2

        # Repeated characters
        import re
        repeats = re.findall(r"(.)\1{3,}", text)
        if repeats:
            score += 0.2

        # Extreme sentiment with no detail
        if sentiment in ("positive", "negative") and len(text) < 30:
            score += 0.15

        return min(score, 0.95)


# ONNX-optimized variant
class BERTONNXPredictor:
    """Optimized BERT predictor using ONNX Runtime."""

    def __init__(self, model_path: str):
        import onnxruntime as ort

        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.session = ort.InferenceSession(
            os.path.join(model_path, "model.onnx"),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]

    def predict(self, text: str) -> dict:
        inputs = self.tokenizer(text, return_tensors="np", truncation=True, max_length=512, padding=True)
        ort_inputs = {name: inputs[name].numpy() for name in self.input_names if name in inputs}
        outputs = self.session.run(self.output_names, ort_inputs)
        probabilities = torch.softmax(torch.tensor(outputs[0]), dim=-1).numpy()[0]
        sentiment_idx = int(np.argmax(probabilities))
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        return {
            "sentiment": sentiment_map[sentiment_idx],
            "sentiment_score": float(probabilities[sentiment_idx]),
            "model_version": "bert-onnx",
        }
