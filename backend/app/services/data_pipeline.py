"""Data pipeline: centralized cleaning, validation, dedup, and normalization.

All comment import paths (crawl, CSV, API) should route through this
module to guarantee consistent data quality before persistence.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

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


class DataPipeline:
    """Stateless pipeline for processing incoming reviews."""

    # Minimum review content length after cleaning
    MIN_REVIEW_LENGTH = 5
    MAX_REVIEW_LENGTH = 10000

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
        # (allow short English/Spanish reviews if they pass length check)
        lang = detect_language(text)
        if lang != "zh" and len(text) < 20:
            # Very short non-Chinese reviews are likely noise
            return None

        # Rating: explicitly check None to avoid treating 0 as missing
        rating_val = review.get("rating")
        if rating_val is None:
            rating_val = review.get("评分")
        rating = normalize_rating(rating_val)
        author = (review.get("author_name") or review.get("author")
                  or review.get("用户名") or "").strip()
        platform = (review.get("platform") or review.get("平台") or "").strip()

        # Parse purchase_time string -> date if needed
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
                      session=None) -> DataPipelineResult:
        """Process a batch of raw review dicts and return dedup results.

        When *session* is provided, DB-level dedup is performed using
        ``filter_existing_hashes``. Otherwise only in-memory dedup is done.
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

            # In-memory dedup (same batch)
            if pr.content_hash in seen_hashes:
                result.skipped_dup += 1
                continue
            seen_hashes.add(pr.content_hash)

            processed.append(pr)

        # DB-level dedup (existing records)
        if session is not None and processed:
            new_hashes = cls.filter_existing_hashes(
                session, product_id, {pr.content_hash for pr in processed}
            )
            kept = [pr for pr in processed if pr.content_hash in new_hashes]
            result.skipped_dup += len(processed) - len(kept)
            processed = kept

        result.new = len(processed)
        return result, processed
