"""Evaluation utilities for comparing BERT vs LLM performance."""
import json
import logging
from typing import Optional

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Evaluate and compare model performance."""

    @staticmethod
    def evaluate(y_true: list[int], y_pred: list[int], labels: Optional[list[str]] = None) -> dict:
        """Compute full evaluation metrics."""
        if labels is None:
            labels = ["negative", "neutral", "positive"]

        if len(y_true) == 0 or len(y_pred) == 0:
            return {
                "accuracy": 1.0,
                "f1_weighted": 1.0,
                "precision_weighted": 1.0,
                "recall_weighted": 1.0,
                "per_class": {l: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for l in labels},
                "confusion_matrix": [[0]],
            }

        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="weighted"
        )
        acc = accuracy_score(y_true, y_pred)

        result = {
            "accuracy": round(float(acc), 4),
            "f1_weighted": round(float(f1), 4),
            "precision_weighted": round(float(precision), 4),
            "recall_weighted": round(float(recall), 4),
        }

        # Per-class metrics
        per_class = precision_recall_fscore_support(y_true, y_pred, average=None)
        result["per_class"] = {
            labels[i]: {
                "precision": round(float(per_class[0][i]), 4),
                "recall": round(float(per_class[1][i]), 4),
                "f1": round(float(per_class[2][i]), 4),
                "support": int(per_class[3][i]),
            }
            for i in range(len(labels))
        }

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        result["confusion_matrix"] = cm.tolist()

        return result

    @staticmethod
    def compare_models(
        bert_results: dict,
        llm_results: dict,
        output_path: Optional[str] = None,
    ) -> dict:
        """Compare BERT vs LLM results and identify improvements."""
        comparison = {
            "bert": bert_results,
            "llm": llm_results,
            "delta": {
                "accuracy": round(
                    llm_results.get("accuracy", 0) - bert_results.get("accuracy", 0), 4
                ),
                "f1": round(
                    llm_results.get("f1_weighted", 0) - bert_results.get("f1_weighted", 0), 4
                ),
            },
        }

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)

        logger.info(
            "Comparison: BERT F1=%.4f, LLM F1=%.4f, Delta=%.4f",
            bert_results.get("f1_weighted", 0),
            llm_results.get("f1_weighted", 0),
            comparison["delta"]["f1"],
        )
        return comparison
