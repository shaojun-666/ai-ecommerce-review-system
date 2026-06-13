"""Data Exporter — batch export crawled data to local files.

Exports products and comments as JSON/CSV to organized local folders.
Supports auto-export at configurable thresholds and manual triggers.

Export directory structure:
    data/exports/
        YYYY-MM-DD_HHMMSS/
            summary.json          # Export manifest
            jd/
                products.json
                comments.json
            taobao/
                products.json
                comments.json
            pdd/
                products.json
                comments.json
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis

logger = logging.getLogger(__name__)

# Default export root (relative to project root)
DEFAULT_EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "exports",
)

# Default: auto-export when total comments grows by this many
DEFAULT_BATCH_THRESHOLD = 500

# Track last export count (in-memory; resets on server restart)
_last_exported_count = 0


def get_last_export_count() -> int:
    global _last_exported_count
    return _last_exported_count


def set_last_export_count(count: int):
    global _last_exported_count
    _last_exported_count = count


class ExportManifest:
    """Metadata for a single export operation."""

    def __init__(self, *, export_dir: str, total_products: int = 0,
                 total_comments: int = 0, platforms: Optional[list[str]] = None):
        self.export_dir = export_dir
        self.exported_at = datetime.now(timezone.utc).isoformat()
        self.total_products = total_products
        self.total_comments = total_comments
        self.platforms = platforms or []

    def to_dict(self) -> dict:
        return {
            "export_dir": self.export_dir,
            "exported_at": self.exported_at,
            "total_products": self.total_products,
            "total_comments": self.total_comments,
            "platforms": self.platforms,
        }


class DataExporter:
    """Export crawled products and comments to local files."""

    def __init__(self, export_dir: str = DEFAULT_EXPORT_DIR):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────────────

    def export_all(self, platforms: Optional[list[str]] = None) -> ExportManifest:
        """Export all crawled data to a timestamped directory.

        Args:
            platforms: Filter to specific platforms (None = all).

        Returns:
            ExportManifest with export info.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        export_path = os.path.join(self.export_dir, timestamp)
        os.makedirs(export_path, exist_ok=True)

        platforms_done = []
        total_products = 0
        total_comments = 0

        for platform in self._get_platforms(platforms):
            platform_dir = os.path.join(export_path, platform)
            os.makedirs(platform_dir, exist_ok=True)

            products = self._export_products(platform, platform_dir)
            comments = self._export_comments(platform, platform_dir)

            if products > 0 or comments > 0:
                platforms_done.append(platform)
                total_products += products
                total_comments += comments
                logger.info("Exported %s: %d products, %d comments", platform, products, comments)

        # Write manifest
        manifest = ExportManifest(
            export_dir=export_path,
            total_products=total_products,
            total_comments=total_comments,
            platforms=platforms_done,
        )
        self._write_json(os.path.join(export_path, "summary.json"), manifest.to_dict())

        logger.info(
            "Export complete: %s — %d products, %d comments across %d platforms",
            export_path, total_products, total_comments, len(platforms_done),
        )
        return manifest

    def check_and_auto_export(self, threshold: int = DEFAULT_BATCH_THRESHOLD) -> Optional[ExportManifest]:
        """Auto-export if new comments since last export exceed threshold.

        Args:
            threshold: Export when new comments >= this number.

        Returns:
            ExportManifest if export was triggered, None otherwise.
        """
        current_count = Comment.query.count()
        last_count = get_last_export_count()

        if last_count == 0:
            set_last_export_count(current_count)
            return None

        new_count = current_count - last_count
        if new_count >= threshold:
            logger.info("Auto-export triggered: %d new comments (threshold: %d)", new_count, threshold)
            manifest = self.export_all()
            set_last_export_count(current_count)
            return manifest

        return None

    def list_exports(self, limit: int = 20) -> list[dict]:
        """List previous export operations."""
        if not os.path.isdir(self.export_dir):
            return []

        exports = []
        for name in sorted(os.listdir(self.export_dir), reverse=True):
            summary_path = os.path.join(self.export_dir, name, "summary.json")
            if os.path.isfile(summary_path):
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        exports.append(json.load(f))
                except (json.JSONDecodeError, OSError):
                    exports.append({"export_dir": name, "error": "corrupt"})
            if len(exports) >= limit:
                break

        return exports

    # ── Internal ─────────────────────────────────────────────────────────

    def _get_platforms(self, platforms: Optional[list[str]] = None) -> list[str]:
        """Get list of platforms to export."""
        if platforms:
            return platforms
        results = db.session.query(Product.platform).distinct().all()
        return [r[0] for r in results if r[0]]

    def _export_products(self, platform: str, export_dir: str) -> int:
        """Export products for a platform as JSON."""
        products = Product.query.filter_by(platform=platform).all()
        if not products:
            return 0

        data = []
        for p in products:
            data.append({
                "id": p.id,
                "name": p.name,
                "platform": p.platform,
                "platform_product_id": p.platform_product_id,
                "url": p.url,
                "image_url": p.image_url,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        self._write_json(os.path.join(export_dir, "products.json"), data)
        return len(data)

    def _export_comments(self, platform: str, export_dir: str) -> int:
        """Export comments for a platform as JSON, including analysis."""
        comments = (
            db.session.query(Comment, CommentAnalysis)
            .outerjoin(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
            .join(Product, Comment.product_id == Product.id)
            .filter(Product.platform == platform)
            .order_by(Comment.created_at.desc())
            .all()
        )

        if not comments:
            return 0

        data = []
        for comment, analysis in comments:
            item = {
                "id": comment.id,
                "product_id": comment.product_id,
                "content": comment.content,
                "rating": comment.rating,
                "author_name": comment.author_name,
                "platform": comment.platform,
                "source": comment.source,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
            }
            if analysis:
                item["analysis"] = {
                    "sentiment": analysis.sentiment,
                    "sentiment_score": analysis.sentiment_score,
                    "fake_score": analysis.fake_score,
                    "keywords": analysis.keywords,
                    "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
                }
            data.append(item)

        self._write_json(os.path.join(export_dir, "comments.json"), data)
        return len(data)

    @staticmethod
    def _write_json(path: str, data):
        """Write data as pretty-printed JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
