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

    # Batch load all referenced comments and products (fix N+1)
    comment_ids = [item.comment_id for item in items if item.comment_id]
    comments = {c.id: c for c in Comment.query.filter(Comment.id.in_(comment_ids)).all()}
    product_ids = {c.product_id for c in comments.values() if c.product_id}
    products = {p.id: p for p in Product.query.filter(Product.id.in_(list(product_ids))).all()}

    results = []
    for item in items:
        r = item.to_dict()
        comment = comments.get(item.comment_id)
        if comment:
            r["comment_content"] = (comment.content or "")[:300]
            product = products.get(comment.product_id)
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


def get_trending_products(limit=4):
    """Get top trending products by comment growth rate (past 14d vs 28d)."""
    from app.services.scoring_service import score_all_products
    from sqlalchemy import func

    scored = score_all_products()
    # Sort by growth rate descending
    scored.sort(key=lambda x: x["dimensions"]["growth"]["growth_rate"], reverse=True)

    results = []
    product_ids = []
    for s in scored[:limit]:
        results.append({
            "id": s["product_id"],
            "name": s["product_name"],
            "platform": s["platform"],
            "composite_score": s["composite_score"],
            "growth_rate": s["dimensions"]["growth"]["growth_rate"],
            "comment_count": 0,  # filled below
            "sentiment_score": s["dimensions"]["sentiment"]["score"],
        })
        product_ids.append(s["product_id"])

    # Batch fill comment counts
    if product_ids:
        counts = dict(
            db.session.query(Comment.product_id, func.count())
            .filter(Comment.product_id.in_(product_ids))
            .group_by(Comment.product_id)
            .all()
        )
        for r in results:
            r["comment_count"] = counts.get(r["id"], 0)

    return results


def get_ai_recommendation():
    """Generate a simple AI selection recommendation based on current data."""
    from app.models.product import Product
    from app.services.scoring_service import score_all_products, detect_uptrend

    total_products = Product.query.count()
    scored = score_all_products()

    if not scored:
        return {"recommendation": "系统中暂无商品数据。开始爬取商品数据后，AI 会为您提供选品建议。"}

    # Find uptrend products — batch load all products
    product_ids = [s["product_id"] for s in scored]
    products = {p.id: p for p in Product.query.filter(Product.id.in_(product_ids)).all()}
    uptrends = []
    for s in scored:
        product = products.get(s["product_id"])
        if product:
            u = detect_uptrend(product, s)
            if u["is_uptrend"]:
                uptrends.append((s, u))

    # Find highest-rated category
    top_product = scored[0] if scored else None

    lines = []
    if uptrends:
        top_trend = uptrends[0]
        lines.append(
            f"「{top_trend[0]['product_name']}」处于上升期，"
            f"综合评分 {top_trend[0]['composite_score']} 分，"
            f"情感评分 {top_trend[0]['dimensions']['sentiment']['score']}%，"
            f"评论增长率 {top_trend[0]['dimensions']['growth']['growth_rate']}%。"
        )

    if len(uptrends) >= 2:
        uptrend_names = "、".join(u[0]["product_name"] for u in uptrends[:3])
        lines.append(f"当前共有 {len(uptrends)} 个商品处于上升期，包括 {uptrend_names} 等，建议重点关注。")

    if total_products > 0:
        # Average sentiment
        avg_sentiment = sum(s["dimensions"]["sentiment"]["score"] for s in scored) / len(scored)
        if avg_sentiment > 60:
            lines.append(f"整体情感评分 {avg_sentiment:.1f}%，用户反馈积极，市场环境良好。")
        elif avg_sentiment > 40:
            lines.append(f"整体情感评分 {avg_sentiment:.1f}%，市场情绪中性偏正面。")
        else:
            lines.append(f"整体情感评分 {avg_sentiment:.1f}%，建议关注负面反馈较多的商品，优化产品和服务。")

    if not lines:
        lines.append(f"系统共有 {total_products} 个商品，暂无明显上升趋势信号。建议增加数据采集量以获取更准确的选品分析。")

    return {"recommendation": " ".join(lines)}


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
