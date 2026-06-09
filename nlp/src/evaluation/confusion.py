"""Confusion matrix utilities."""
import json
import numpy as np
from sklearn.metrics import confusion_matrix


def compute_confusion_matrix(y_true, y_pred, labels=None):
    return confusion_matrix(y_true, y_pred, labels=labels)


def confusion_to_dict(cm, labels=None):
    if labels is None:
        labels = ["negative", "neutral", "positive"]

    result = {"labels": labels, "matrix": cm.tolist()}

    for i, true_label in enumerate(labels):
        total = int(cm[i].sum()) or 1
        for j, pred_label in enumerate(labels):
            key = f"{true_label}_as_{pred_label}"
            result[key] = {"count": int(cm[i][j]), "percentage": round(float(cm[i][j]) / total * 100, 1)}

    return result


def find_confused_pairs(cm, labels=None):
    if labels is None:
        labels = ["negative", "neutral", "positive"]

    pairs = []
    for i in range(len(labels)):
        for j in range(len(labels)):
            if i != j and cm[i][j] > 0:
                pairs.append({
                    "true": labels[i],
                    "predicted": labels[j],
                    "count": int(cm[i][j]),
                })

    return sorted(pairs, key=lambda x: -x["count"])
