"""Celery tasks for sentiment analysis."""
import datetime
import logging
from app.tasks import celery_app
from app.extensions import db
from app.models.analysis_task import AnalysisTask
from app.models.comment import Comment, CommentAnalysis
from app.services.sentiment_service import SentimentService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_analysis(self, task_id: int, comment_ids: list[int],
                 model_path: str = "./nlp/models",
                 model_name: str = "bert-base-chinese"):
    """Run sentiment analysis on a batch of comments."""
    task = db.session.get(AnalysisTask, task_id)
    if not task:
        logger.error("Task %s not found", task_id)
        return {"error": "Task not found"}

    try:
        service = SentimentService(model_path=model_path, model_name=model_name)
    except RuntimeError as e:
        task.status = "failed"
        task.completed_at = datetime.datetime.utcnow()
        task.result_summary = {"error": str(e)}
        db.session.commit()
        return {"error": str(e)}

    task.status = "processing"
    task.timeout_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    db.session.commit()

    processed = 0
    failed = 0
    errors = []

    for comment_id in comment_ids:
        try:
            comment = db.session.get(Comment, comment_id)
            if not comment:
                continue

            result = service.analyze(comment.content)

            analysis = CommentAnalysis.query.filter_by(comment_id=comment_id).first()
            if not analysis:
                analysis = CommentAnalysis(comment_id=comment_id)
                db.session.add(analysis)

            analysis.task_id = task_id
            analysis.sentiment = result.get("sentiment")
            analysis.sentiment_score = result.get("sentiment_score")
            analysis.aspects = result.get("aspects")
            analysis.keywords = result.get("keywords")
            analysis.summary = result.get("summary")
            analysis.fake_score = result.get("fake_score")
            analysis.model_version = result.get("model_version")
            analysis.analyzed_at = datetime.datetime.utcnow()

            processed += 1
            task.processed_count = processed

            if processed % 50 == 0:
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            failed += 1
            errors.append({"comment_id": comment_id, "error": str(e)})
            logger.error("Failed to analyze comment %s: %s", comment_id, str(e))

    task.processed_count = processed
    task.failed_count = failed
    task.error_count = failed
    task.status = "completed_with_errors" if failed > 0 else "completed"
    task.completed_at = datetime.datetime.utcnow()
    task.result_summary = {
        "total": len(comment_ids),
        "processed": processed,
        "failed": failed,
        "errors": errors[:10],
    }
    db.session.commit()
    return task.result_summary
