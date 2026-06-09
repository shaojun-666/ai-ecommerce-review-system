import csv
import io
import chardet
from datetime import datetime, timezone
from app.extensions import db
from app.models.comment import Comment, CommentAnalysis
from app.models.product import Product
from app.utils.errors import NotFound


class CommentImportResult:
    def __init__(self):
        self.total = 0
        self.imported = 0
        self.skipped = 0
        self.errors = []


def import_comments_from_csv(file_storage, product_id, user_id=None):
    result = CommentImportResult()
    product = db.session.get(Product, product_id)
    if not product:
        raise NotFound("Product not found")

    raw = file_storage.read()
    encoding = chardet.detect(raw)["encoding"] or "utf-8"
    try:
        content = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        content = raw.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(content))
    now = datetime.now(timezone.utc)
    batch = []
    for line_no, row in enumerate(reader, start=2):
        result.total += 1
        try:
            text = (row.get("content") or row.get("评论内容") or "").strip()
            if not text:
                result.skipped += 1
                result.errors.append(f"Line {line_no}: empty comment content")
                continue

            rating_raw = row.get("rating") or row.get("评分") or ""
            try:
                rating = int(float(rating_raw)) if rating_raw else None
            except (ValueError, TypeError):
                rating = None

            if rating is not None and (rating < 1 or rating > 5):
                result.errors.append(f"Line {line_no}: rating {rating} out of range 1-5")
                rating = None

            author = (row.get("author_name") or row.get("author") or row.get("用户名") or "").strip()
            platform = (row.get("platform") or row.get("平台") or product.platform or "").strip()

            comment = Comment(
                product_id=product.id,
                user_id=user_id,
                content=text,
                rating=rating,
                author_name=author,
                platform=platform,
                source="import",
                created_at=now,
            )
            batch.append(comment)
            result.imported += 1

            if len(batch) >= 500:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                batch = []

        except Exception as e:
            db.session.rollback()
            result.errors.append(f"Line {line_no}: {str(e)}")
            result.skipped += 1

    if batch:
        try:
            db.session.bulk_save_objects(batch)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            result.errors.append(f"Batch commit error: {str(e)}")
            result.skipped += len(batch)
            result.imported -= len(batch)

    return result


def get_comments_query(filters=None):
    q = Comment.query
    if filters:
        if filters.get("product_id"):
            q = q.filter(Comment.product_id == filters["product_id"])
        if filters.get("platform"):
            q = q.filter(Comment.platform == filters["platform"])
        if filters.get("sentiment"):
            q = q.join(CommentAnalysis).filter(CommentAnalysis.sentiment == filters["sentiment"])
        if filters.get("rating"):
            q = q.filter(Comment.rating == int(filters["rating"]))
        if filters.get("keyword"):
            q = q.filter(Comment.content.ilike(f"%{filters['keyword']}%"))
        if filters.get("start_date"):
            q = q.filter(Comment.created_at >= filters["start_date"])
        if filters.get("end_date"):
            q = q.filter(Comment.created_at <= filters["end_date"])
        if filters.get("min_fake_score"):
            q = q.join(CommentAnalysis).filter(CommentAnalysis.fake_score >= float(filters["min_fake_score"]))
    return q.order_by(Comment.created_at.desc())


def export_comments_csv(comments):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "content", "rating", "platform", "author", "created_at", "sentiment", "fake_score"])
    for c in comments:
        analysis = c.analysis if hasattr(c, "analysis") and c.analysis else None
        writer.writerow([
            c.id,
            c.content.replace('"', '""') if c.content else "",
            c.rating,
            c.platform,
            c.author_name,
            c.created_at.isoformat() if c.created_at else "",
            analysis.sentiment if analysis else "",
            f"{analysis.fake_score:.2f}" if analysis and analysis.fake_score is not None else "",
        ])
    return output.getvalue()
