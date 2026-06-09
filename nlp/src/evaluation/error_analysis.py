"""Error analysis for model prediction failures."""
from typing import Optional


class ErrorAnalyzer:
    def __init__(self, label_map: Optional[dict] = None):
        self.label_map = label_map or {0: "negative", 1: "neutral", 2: "positive"}

    def analyze_bad_cases(self, texts: list[str], y_true: list[int], y_pred: list[int], scores: Optional[list[float]] = None):
        bad_cases = []
        for i, (true, pred) in enumerate(zip(y_true, y_pred)):
            if true != pred:
                bad_cases.append({
                    "text": texts[i][:200] if texts[i] else "",
                    "true_label": self.label_map.get(true, str(true)),
                    "pred_label": self.label_map.get(pred, str(pred)),
                    "confidence": float(scores[i]) if scores and i < len(scores) else None,
                })
        return bad_cases

    def summarize_errors(self, bad_cases: list[dict]) -> dict:
        if not bad_cases:
            return {"total": 0, "confusion_summary": {}, "high_confidence_errors": 0}

        confusion = {}
        for case in bad_cases:
            key = f"{case['true_label']}→{case['pred_label']}"
            confusion[key] = confusion.get(key, 0) + 1

        high_conf = sum(
            1 for c in bad_cases
            if c.get("confidence") is not None and c["confidence"] > 0.9
        )

        return {
            "total": len(bad_cases),
            "confusion_summary": dict(sorted(confusion.items(), key=lambda x: -x[1])),
            "high_confidence_errors": high_conf,
        }
