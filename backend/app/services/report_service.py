import csv
import io
from datetime import datetime, timezone
from app.extensions import db
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask
from app.utils.errors import NotFound


def generate_excel_report(task_id):
    task = db.session.get(AnalysisTask, task_id)
    if not task:
        raise NotFound("Analysis task not found")

    analyses = CommentAnalysis.query.filter(
        CommentAnalysis.task_id == task_id
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "comment_id", "content", "rating", "sentiment", "sentiment_score",
        "aspects", "keywords", "summary", "fake_score", "model_version",
    ])

    for a in analyses:
        comment = db.session.get(Comment, a.comment_id)
        writer.writerow([
            a.comment_id,
            comment.content.replace('"', '""') if comment and comment.content else "",
            comment.rating if comment else "",
            a.sentiment,
            a.sentiment_score,
            str(a.aspects or ""),
            ",".join(a.keywords) if a.keywords else "",
            a.summary or "",
            a.fake_score,
            a.model_version or "",
        ])

    return output.getvalue()


def generate_summary_report(overview_data, trend_data, keyword_data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["=== AI E-commerce Review Analysis Report ==="])
    writer.writerow([f"Generated: {datetime.now(timezone.utc).isoformat()}"])
    writer.writerow([])

    writer.writerow(["Overview"])
    writer.writerow(["Total Comments", overview_data.get("total_comments", 0)])
    writer.writerow(["Analyzed Count", overview_data.get("analyzed_count", 0)])
    writer.writerow(["Avg Rating", overview_data.get("avg_rating", 0)])
    writer.writerow(["Fake Reviews", overview_data.get("fake_review_count", 0)])

    dist = overview_data.get("sentiment_distribution", {})
    for label in ["positive", "negative", "neutral"]:
        item = dist.get(label, {})
        writer.writerow([f"{label} count", item.get("count", 0)])
        writer.writerow([f"{label} percentage", f'{item.get("percentage", 0)}%'])

    writer.writerow([])
    writer.writerow(["Top Keywords"])
    for kw in keyword_data[:20]:
        writer.writerow([kw.get("word"), kw.get("count", 0)])

    return output.getvalue()
