"""Reusable evaluation metric functions."""
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)


def classification_metrics(y_true, y_pred, average: str = "weighted"):
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average=average
    )
    acc = accuracy_score(y_true, y_pred)
    return {
        "accuracy": float(acc),
        "f1": float(f1),
        "precision": float(precision),
        "recall": float(recall),
    }


def binary_auc(y_true, y_scores):
    try:
        return float(roc_auc_score(y_true, y_scores))
    except ValueError:
        return 0.0


def regression_metrics(y_true, y_pred):
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    return {
        "mse": float(mean_squared_error(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }
