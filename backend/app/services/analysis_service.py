from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask
from app.models.product import Product
from app.utils.errors import NotFound


def create_analysis_task(user_id, comment_ids, name=None, analysis_type="full"):
    task = AnalysisTask(
        user_id=user_id,
        name=name or f"Analysis {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        status="pending",
        total_count=len(comment_ids),
        processed_count=0,
        failed_count=0,
        error_count=0,
        timeout_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(task)
    db.session.commit()
    return task


def get_task_progress(task_id):
    task = db.session.get(AnalysisTask, task_id)
    if not task:
        raise NotFound("Analysis task not found")
    return task


def get_task_results(task_id, page=1, per_page=20):
    task = db.session.get(AnalysisTask, task_id)
    if not task:
        raise NotFound("Analysis task not found")

    query = CommentAnalysis.query.filter(
        CommentAnalysis.task_id == task_id
    ).order_by(CommentAnalysis.id.desc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for item in items:
        r = item.to_dict()
        comment = db.session.get(Comment, item.comment_id)
        if comment:
            r["comment_content"] = comment.content[:300] if comment.content else ""
            product = db.session.get(Product, comment.product_id)
            r["product_name"] = product.name if product else ""
        results.append(r)

    return results, total, page, per_page


def get_dashboard_overview():
    total_comments = Comment.query.count()
    analyzed = CommentAnalysis.query.count()
    total_tasks = AnalysisTask.query.count()

    positive = CommentAnalysis.query.filter(CommentAnalysis.sentiment == "positive").count()
    negative = CommentAnalysis.query.filter(CommentAnalysis.sentiment == "negative").count()
    neutral = CommentAnalysis.query.filter(CommentAnalysis.sentiment == "neutral").count()
    analyzed_total = positive + negative + neutral or 1

    avg_rating = db.session.query(db.func.avg(Comment.rating)).scalar() or 0

    fake_count = CommentAnalysis.query.filter(CommentAnalysis.fake_score >= 0.7).count()

    return {
        "total_comments": total_comments,
        "analyzed_count": analyzed,
        "total_tasks": total_tasks,
        "sentiment_distribution": {
            "positive": {"count": positive, "percentage": round(positive / analyzed_total * 100, 1)},
            "negative": {"count": negative, "percentage": round(negative / analyzed_total * 100, 1)},
            "neutral": {"count": neutral, "percentage": round(neutral / analyzed_total * 100, 1)},
        },
        "avg_rating": round(float(avg_rating), 2),
        "fake_review_count": fake_count,
    }


def get_trend_data(days=30):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    results = (
        db.session.query(
            db.func.date(CommentAnalysis.analyzed_at).label("date"),
            CommentAnalysis.sentiment,
            db.func.count().label("count"),
        )
        .filter(CommentAnalysis.analyzed_at >= start)
        .group_by("date", CommentAnalysis.sentiment)
        .order_by("date")
        .all()
    )

    trend_map = {}
    for r in results:
        d = r.date.isoformat()[:10]
        if d not in trend_map:
            trend_map[d] = {"date": d, "positive": 0, "negative": 0, "neutral": 0}
        if r.sentiment in trend_map[d]:
            trend_map[d][r.sentiment] = r.count

    return sorted(trend_map.values(), key=lambda x: x["date"])


def get_latest_comments(limit=10):
    """Return the most recently analyzed comments with sentiment labels."""
    rows = (
        db.session.query(
            CommentAnalysis.comment_id,
            CommentAnalysis.sentiment,
            CommentAnalysis.sentiment_score,
            CommentAnalysis.fake_score,
            Comment.content,
            Product.name.label("product_name"),
            CommentAnalysis.analyzed_at,
        )
        .join(Comment, CommentAnalysis.comment_id == Comment.id)
        .join(Product, Comment.product_id == Product.id)
        .filter(CommentAnalysis.analyzed_at.isnot(None))
        .order_by(CommentAnalysis.analyzed_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "comment_id": r.comment_id,
            "content": (r.content or "")[:100],
            "sentiment": r.sentiment,
            "sentiment_score": round(float(r.sentiment_score), 4) if r.sentiment_score else None,
            "fake_score": round(float(r.fake_score), 4) if r.fake_score else None,
            "product_name": r.product_name or "",
            "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
        }
        for r in rows
    ]


def get_keyword_rank(limit=30):
    rows = (
        db.session.query(CommentAnalysis.keywords)
        .filter(CommentAnalysis.keywords.isnot(None))
        .limit(1000)
        .all()
    )

    word_count = {}
    for row in rows:
        if isinstance(row.keywords, list):
            for kw in row.keywords:
                word_count[kw] = word_count.get(kw, 0) + 1

    sorted_words = sorted(word_count.items(), key=lambda x: -x[1])[:limit]
    return [{"word": w, "count": c} for w, c in sorted_words]
