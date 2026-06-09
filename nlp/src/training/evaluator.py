"""Evaluation module for model validation during training."""
import torch
import numpy as np
from torch.utils.data import DataLoader
from transformers import BertTokenizer
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix


class Evaluator:
    def __init__(self, model, tokenizer, device: str = "cpu"):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.model.to(device)
        self.model.eval()

    @torch.no_grad()
    def evaluate(self, texts: list[str], labels: list[int]) -> dict:
        inputs = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=128,
            return_tensors="pt",
        ).to(self.device)

        outputs = self.model(**inputs)
        predictions = torch.argmax(outputs.logits, dim=-1).cpu().numpy()

        acc = accuracy_score(labels, predictions)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average="weighted"
        )
        cm = confusion_matrix(labels, predictions)

        return {
            "accuracy": float(acc),
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "confusion_matrix": cm.tolist(),
        }

    @torch.no_grad()
    def predict(self, text: str) -> dict:
        inputs = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=128,
            return_tensors="pt",
        ).to(self.device)

        outputs = self.model(**inputs)
        probabilities = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
        sentiment_idx = int(np.argmax(probabilities))
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        return {
            "sentiment": sentiment_map[sentiment_idx],
            "score": float(probabilities[sentiment_idx]),
            "probabilities": probabilities.tolist(),
        }
