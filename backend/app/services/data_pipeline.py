"""Data pipeline: centralized cleaning, validation, dedup, freshness tracking, and normalization.

All comment import paths (crawl, CSV, API) should route through this
module to guarantee consistent data quality before persistence.
"""
import logging
from typing import Optional
from datetime import datetime, timezone, date, timedelta

from app.utils.text_cleaner import clean_text, normalize_rating, is_valid_review, detect_language, content_hash

logger = logging.getLogger(__name__)


class ProcessedReview:
    """Normalized review record ready for DB insertion."""

    def __init__(self, *, content: str, content_hash: str, rating: Optional[int] = None,
                 author_name: str = "", platform: str = "", source: str = "import",
                 purchase_time=None):
        self.content = content
        self.content_hash = content_hash
        self.rating = rating
        self.author_name = author_name
        self.platform = platform
        self.source = source
        self.purchase_time = purchase_time


class DataPipelineResult:
    """Result of a batch processing run."""

    def __init__(self):
        self.total = 0
        self.new = 0
        self.skipped_dup = 0
        self.filtered = 0
        self.errors = []

    @property
    def skipped(self):
        """Total skipped = duplicates + filtered."""
        return self.skipped_dup + self.filtered


class DataFreshnessInfo:
    """Data freshness metadata for a product."""

    def __init__(self, *, product_id: int, last_crawled_at: Optional[datetime] = None,
                 total_comments: int = 0, recent_comments: int = 0,
                 stale_days: Optional[int] = None):
        self.product_id = product_id
        self.last_crawled_at = last_crawled_at
        self.total_comments = total_comments
        self.recent_comments = recent_comments
        self.stale_days = stale_days

    @property
    def is_stale(self) -> bool:
        """A product is stale if it hasn't been crawled in 7+ days."""
        if self.stale_days is None:
            return True
        return self.stale_days >= 7

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "last_crawled_at": self.last_crawled_at.isoformat() if self.last_crawled_at else None,
            "total_comments": self.total_comments,
            "recent_comments": self.recent_comments,
            "stale_days": self.stale_days,
            "is_stale": self.is_stale,
        }


class DataQualityReport:
    """Quality metrics for a data pipeline run."""

    def __init__(self):
        self.total_products = 0
        self.total_comments = 0
        self.duplicate_rate = 0.0
        self.filter_rate = 0.0
        self.stale_products = 0
        self.freshness_by_platform = {}

    def to_dict(self):
        return {
            "total_products": self.total_products,
            "total_comments": self.total_comments,
            "duplicate_rate": round(self.duplicate_rate, 4),
            "filter_rate": round(self.filter_rate, 4),
            "stale_products": self.stale_products,
            "freshness_by_platform": self.freshness_by_platform,
        }


class DataPipeline:
    """Stateless pipeline for processing incoming reviews and tracking data health."""

    # Minimum review content length after cleaning
    MIN_REVIEW_LENGTH = 5
    MAX_REVIEW_LENGTH = 10000

    # Staleness threshold in days
    STALE_DAYS = 7

    @classmethod
    def process_review(cls, review: dict, product_id: int) -> Optional[ProcessedReview]:
        """Process a single raw review dict.

        Cleans text, validates, computes hash, and returns a normalized
        ``ProcessedReview``. Returns ``None`` when the review is invalid.

        Accepts field names from both crawl results and CSV import:
          - content / 评论内容
          - rating / 评分
          - author_name / author / 用户名
          - platform / 平台
          - purchase_time
        """
        text = review.get("content") or review.get("评论内容") or ""
        text = clean_text(text)

        if not is_valid_review(text, cls.MIN_REVIEW_LENGTH, cls.MAX_REVIEW_LENGTH):
            return None

        # Language check — only accept Chinese or longer non-Chinese
        lang = detect_language(text)
        if lang != "zh" and len(text) < 20:
            return None

        rating_val = review.get("rating")
        if rating_val is None:
            rating_val = review.get("评分")
        rating = normalize_rating(rating_val)
        author = (review.get("author_name") or review.get("author")
                  or review.get("用户名") or "").strip()
        platform = (review.get("platform") or review.get("平台") or "").strip()

        pt = review.get("purchase_time")
        if isinstance(pt, str):
            try:
                pt = datetime.strptime(pt, "%Y-%m-%d").date()
            except ValueError:
                pt = None

        h = content_hash(text)

        return ProcessedReview(
            content=text,
            content_hash=h,
            rating=rating,
            author_name=author,
            platform=platform,
            source=review.get("source", "import"),
            purchase_time=pt,
        )

    @classmethod
    def filter_existing_hashes(cls, session, product_id: int, hashes: set[str]) -> set[str]:
        """Query the DB for which hashes already exist for a product.

        Returns the subset of ``hashes`` that are *new* (not yet in DB).
        """
        if not hashes:
            return set()

        from app.models.comment import Comment
        existing = set(
            row[0] for row in session.query(Comment.content_hash)
            .filter(
                Comment.product_id == product_id,
                Comment.content_hash.in_(list(hashes)),
            )
            .all()
            if row[0]
        )
        return hashes - existing

    @classmethod
    def process_batch(cls, reviews: list[dict], product_id: int,
                      session=None) -> tuple:
        """Process a batch of raw review dicts and return dedup results.

        When *session* is provided, DB-level dedup is performed using
        ``filter_existing_hashes``. Otherwise only in-memory dedup is done.

        Returns (DataPipelineResult, list[ProcessedReview]).
        """
        result = DataPipelineResult()
        result.total = len(reviews)

        processed: list[ProcessedReview] = []
        seen_hashes: set[str] = set()

        for review in reviews:
            pr = cls.process_review(review, product_id)
            if pr is None:
                result.filtered += 1
                continue

            if pr.content_hash in seen_hashes:
                result.skipped_dup += 1
                continue
            seen_hashes.add(pr.content_hash)

            processed.append(pr)

        if session is not None and processed:
            new_hashes = cls.filter_existing_hashes(
                session, product_id, {pr.content_hash for pr in processed}
            )
            kept = [pr for pr in processed if pr.content_hash in new_hashes]
            result.skipped_dup += len(processed) - len(kept)
            processed = kept

        result.new = len(processed)
        return result, processed

    # ------------------------------------------------------------------
    # Data Freshness
    # ------------------------------------------------------------------

    @classmethod
    def get_freshness_info(cls, product_id: int) -> DataFreshnessInfo:
        """Get data freshness info for a single product."""
        from app.extensions import db
        from app.models.product import Product
        from app.models.comment import Comment

        product = Product.query.get(product_id)
        if not product:
            return DataFreshnessInfo(product_id=product_id)

        total = Comment.query.filter(Comment.product_id == product_id).count()
        recent = Comment.query.filter(
            Comment.product_id == product_id,
            Comment.created_at >= datetime.now(timezone.utc) - timedelta(days=cls.STALE_DAYS),
        ).count()

        stale_days = None
        if product.last_crawled_at:
            delta = datetime.now(timezone.utc) - product.last_crawled_at
            stale_days = delta.days

        return DataFreshnessInfo(
            product_id=product_id,
            last_crawled_at=product.last_crawled_at,
            total_comments=total,
            recent_comments=recent,
            stale_days=stale_days,
        )

    @classmethod
    def get_stale_products(cls, stale_days: int = 7) -> list[dict]:
        """List products that haven't been crawled in *stale_days* days."""
        from app.extensions import db
        from app.models.product import Product

        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        products = Product.query.filter(
            db.or_(
                Product.last_crawled_at == None,
                Product.last_crawled_at < cutoff,
            )
        ).all()
        return [p.to_dict() for p in products]

    @classmethod
    def compute_quality_report(cls) -> DataQualityReport:
        """Compute overall data quality metrics."""
        from app.extensions import db
        from app.models.product import Product
        from app.models.comment import Comment
        from sqlalchemy import func, text

        report = DataQualityReport()

        report.total_products = Product.query.count()
        report.total_comments = Comment.query.count()

        # Duplicate rate: comments with duplicate content_hash per product
        dup_result = db.session.execute(
            text("""
                SELECT COUNT(*) - COUNT(DISTINCT content_hash) AS dup_count
                FROM comments
                WHERE content_hash IS NOT NULL AND content_hash != ''
            """)
        ).scalar() or 0
        report.duplicate_rate = dup_result / max(report.total_comments, 1)

        # Filter rate: how many reviews get filtered out (estimate via data_pipeline stats)
        # We can't know this historically, report 0 if no data
        report.filter_rate = 0.0

        # Freshness by platform
        platforms = db.session.query(Product.platform, func.count(Product.id)).group_by(Product.platform).all()
        for platform, cnt in platforms:
            if not platform:
                continue
            # Count stale products per platform
            cutoff = datetime.now(timezone.utc)
            stale = db.session.query(func.count(Product.id)).filter(
                Product.platform == platform,
                db.or_(
                    Product.last_crawled_at == None,
                    Product.last_crawled_at < cutoff,
                )
            ).scalar() or 0
            report.freshness_by_platform[platform] = {
                "total": cnt,
                "stale": stale,
                "fresh": cnt - stale,
            }
            report.stale_products += stale

        return report

    @classmethod
    def mark_crawled(cls, product_id: int):
        """Update product's last_crawled_at timestamp after a successful crawl."""
        from app.extensions import db
        from app.models.product import Product

        product = Product.query.get(product_id)
        if product:
            product.last_crawled_at = datetime.now(timezone.utc)
            product.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            # Invalidate dashboard caches
            from app.utils.cache import cache_delete_pattern
            cache_delete_pattern("dashboard:*")
            logger.info("Marked product %d as crawled at %s, caches invalidated", product_id, product.last_crawled_at)


# Backward-compatible aliases
process_review = DataPipeline.process_review
process_batch = DataPipeline.process_batch
filter_existing_hashes = DataPipeline.filter_existing_hashes
