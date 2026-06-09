"""Unified inference interface for BERT and LLM models."""
import logging
from typing import Optional

import torch
import numpy as np
from transformers import BertTokenizer, BertForSequenceClassification

logger = logging.getLogger(__name__)


class InferencePredictor:
    """Unified predictor supporting BERT and ONNX backends."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "bert-base-chinese",
        device: Optional[str] = None,
        use_onnx: bool = False,
        num_labels: int = 3,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_onnx = use_onnx

        if use_onnx:
            self._load_onnx(model_path or model_name)
        else:
            self._load_pytorch(model_path, model_name, num_labels)

        self.aspect_keywords = {
            "quality": ["质量", "做工", "材质", "耐用", "手感", "品质", "结实", "完好"],
            "logistics": ["物流", "快递", "送货", "配送", "发货", "速度", "包装", "运输"],
            "service": ["客服", "服务", "态度", "售后", "退换", "回复", "处理", "耐心"],
            "price": ["价格", "性价比", "划算", "便宜", "贵", "优惠", "折扣", "值"],
        }

    def _load_pytorch(self, model_path, model_name, num_labels):
        self.tokenizer = BertTokenizer.from_pretrained(model_path or model_name)
        self.model = BertForSequenceClassification.from_pretrained(
            model_path or model_name, num_labels=num_labels
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info("PyTorch BERT model loaded on %s", self.device)

    def _load_onnx(self, model_path):
        import onnxruntime as ort

        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.ort_session = ort.InferenceSession(
            f"{model_path}/model.onnx",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        logger.info("ONNX model loaded from %s", model_path)

    @torch.no_grad()
    def predict(self, text: str) -> dict:
        if self.use_onnx:
            return self._predict_onnx(text)
        return self._predict_pytorch(text)

    def _predict_pytorch(self, text: str) -> dict:
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512, padding=True
        ).to(self.device)

        outputs = self.model(**inputs)
        probabilities = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]

        sentiment_idx = int(np.argmax(probabilities))
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        return {
            "sentiment": sentiment_map[sentiment_idx],
            "sentiment_score": float(probabilities[sentiment_idx]),
            "probabilities": {
                "negative": float(probabilities[0]),
                "neutral": float(probabilities[1]),
                "positive": float(probabilities[2]),
            },
            "model_version": "bert-pytorch",
        }

    def _predict_onnx(self, text: str) -> dict:
        inputs = self.tokenizer(text, return_tensors="np", truncation=True, max_length=512, padding=True)
        ort_inputs = {name: inputs[name] for name in self.ort_session.get_inputs() if name in inputs}
        outputs = self.ort_session.run(None, ort_inputs)
        probabilities = torch.softmax(torch.tensor(outputs[0]), dim=-1).numpy()[0]

        sentiment_idx = int(np.argmax(probabilities))
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        return {
            "sentiment": sentiment_map[sentiment_idx],
            "sentiment_score": float(probabilities[sentiment_idx]),
            "model_version": "bert-onnx",
        }

    def predict_batch(self, texts: list[str]) -> list[dict]:
        return [self.predict(t) for t in texts]
