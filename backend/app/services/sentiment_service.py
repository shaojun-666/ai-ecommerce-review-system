"""Sentiment analysis service — calls NLP inference layer."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SentimentService:
    """Service layer for sentiment analysis. Delegates to NLP inference module."""

    def __init__(self, model_path: str = "./nlp/models", model_name: str = "bert-base-chinese"):
        self.model_path = model_path
        self.model_name = model_name
        self.model_type = None
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the NLP model based on config."""
        try:
            from nlp.src.models.bert.model import BERTPredictor

            self.model = BERTPredictor(model_name=self.model_name, model_path=self.model_path)
            self.model_type = "bert"
            logger.info("Loaded BERT model: %s", self.model_name)
        except Exception as e:
            logger.warning("Failed to load NLP model: %s", str(e))
            raise RuntimeError(f"NLP model unavailable: {e}")

    def analyze(self, text: str) -> dict:
        """Analyze a single comment. Returns dict with sentiment, aspects, keywords, etc."""
        if self.model is None:
            raise RuntimeError("NLP model not loaded")
        return self.model.predict(text)

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        """Analyze multiple comments."""
        return [self.analyze(t) for t in texts]
