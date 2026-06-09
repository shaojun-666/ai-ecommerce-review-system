"""Post-processing for NLP model outputs."""


def format_sentiment_result(raw_prediction: dict) -> dict:
    return {
        "sentiment": raw_prediction.get("sentiment", "neutral"),
        "sentiment_score": round(raw_prediction.get("sentiment_score", 0), 4),
        "aspects": raw_prediction.get("aspects", {}),
        "keywords": raw_prediction.get("keywords", []),
        "summary": raw_prediction.get("summary"),
        "fake_score": round(raw_prediction.get("fake_score", 0), 4),
        "model_version": raw_prediction.get("model_version", "unknown"),
    }


def format_batch_results(raw_results: list[dict]) -> list[dict]:
    return [format_sentiment_result(r) for r in raw_results]


def merge_with_heuristic(nlp_result: dict, text: str) -> dict:
    import re
    score = nlp_result.get("fake_score", 0)

    if len(text) < 10:
        score = max(score, 0.3)
    if text.count("!") + text.count("！") > 5:
        score = min(score + 0.1, 1.0)
    if re.search(r"(.)\1{4,}", text):
        score = min(score + 0.1, 1.0)

    nlp_result["fake_score"] = round(score, 4)
    return nlp_result
