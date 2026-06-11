"""Celery tasks for e-commerce data crawling.

Provides:
    - run_crawl: Crawl a single product (triggered by API or Celery Beat)
    - check_crawl_timeouts: Periodic task to mark hung tasks as failed
"""
import logging
import traceback
from datetime import timedelta

from app.tasks import celery_app
from app.extensions import db
from app.models.crawl_task import CrawlTask
from app.models.product import Product
from app.models.comment import Comment
from app.crawler.adapters.jd import JDCrawler
from app.services.data_pipeline import DataPipeline
from app.utils.cache import cache_delete_pattern
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_crawl(self, crawl_task_id: int):
    """Execute a crawl task.

    Flow:
        1. Load CrawlTask from DB (mark as crawling)
        2. Instantiate appropriate crawler (JD only for now)
        3. Run crawl_all(product_url, page_limit)
        4. If product extracted → upsert Product record
        5. If reviews extracted → batch insert Comment records (no duplicate content)
        6. Update CrawlTask with results

    Args:
        crawl_task_id: ID of the CrawlTask record.
    """
    task = db.session.get(CrawlTask, crawl_task_id)
    if not task:
        logger.error("CrawlTask %s not found", crawl_task_id)
        return {"error": "CrawlTask not found"}

    if not task.can_start():
        logger.warning("CrawlTask %s cannot start (status=%s)", crawl_task_id, task.status)
        return {"error": f"Task cannot start (status={task.status})"}

    # Mark as crawling
    task.status = "crawling"
    task.started_at = utcnow()
    task.celery_task_id = self.request.id
    task.error_message = None
    db.session.commit()

    try:
        # Select crawler based on platform
        if task.platform == "jd":
            crawler = JDCrawler()
        else:
            raise ValueError(f"Unsupported platform: {task.platform}")

        # Execute crawl
        result = crawler.crawl_all(task.url, page_limit=task.page_limit or 5)

        if result.blocked:
            task.status = "failed"
            task.error_message = f"Blocked by anti-bot: {result.error}"
            task.completed_at = utcnow()
            db.session.commit()
            return {"error": task.error_message}

        if result.error and not result.product:
            task.status = "failed"
            task.error_message = result.error
            task.completed_at = utcnow()
            db.session.commit()
            return {"error": result.error}

        # Upsert Product
        product = None
        if result.product:
            platform_id = result.product.get("platform_product_id", "")
            product = Product.query.filter_by(
                platform="jd",
                platform_product_id=platform_id,
            ).first() if platform_id else None

            if not product:
                product = Product(
                    name=result.product.get("name", task.name),
                    platform="jd",
                    platform_product_id=platform_id or "",
                    user_id=task.user_id,
                )
                db.session.add(product)
                db.session.flush()

            # Update task product link
            task.product_id = product.id

        # Insert comments via DataPipeline
        new_count = 0
        fail_count = 0
        if product and result.reviews:
            # Set source for pipeline
            for r in result.reviews:
                r.setdefault("source", "crawl")

            pipeline_result, processed = DataPipeline.process_batch(
                result.reviews, product.id, session=db.session,
            )

            # Bulk insert processed reviews
            if processed:
                batch_size = 50
                for i in range(0, len(processed), batch_size):
                    batch = processed[i:i + batch_size]
                    try:
                        db.session.bulk_save_objects([
                            Comment(
                                product_id=product.id,
                                content=pr.content,
                                content_hash=pr.content_hash,
                                rating=pr.rating,
                                author_name=pr.author_name,
                                platform=pr.platform or "jd",
                                source=pr.source,
                                purchase_time=pr.purchase_time,
                            )
                            for pr in batch
                        ])
                        db.session.commit()
                        new_count += len(batch)
                    except Exception as e:
                        db.session.rollback()
                        fail_count += len(batch)
                        logger.error("Batch insert failed: %s", e)

            # Log filtering stats
            if pipeline_result.filtered:
                logger.info(
                    "Filtered %d invalid reviews (total=%d, dup=%d, filtered=%d)",
                    pipeline_result.filtered, pipeline_result.total,
                    pipeline_result.skipped_dup, pipeline_result.filtered,
                )

        # Update task status
        task.status = "completed"
        task.items_found = result.items_found
        task.items_new = new_count
        task.items_failed = fail_count
        task.current_page = result.current_page
        task.total_pages = result.total_pages
        task.last_run_at = utcnow()
        task.completed_at = utcnow()
        task.result_summary = {
            "items_found": result.items_found,
            "items_new": new_count,
            "items_failed": fail_count,
            "pages_crawled": result.current_page,
            "total_pages": result.total_pages,
            "has_product": result.product is not None,
        }
        db.session.commit()

        # Invalidate dashboard cache so next request gets fresh data
        cache_delete_pattern("dashboard:*")

        logger.info(
            "CrawlTask %s completed: %d found, %d new, %d failed",
            crawl_task_id, result.items_found, new_count, fail_count,
        )
        return task.result_summary

    except Exception as e:
        db.session.rollback()
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = utcnow()
        db.session.commit()
        logger.error("CrawlTask %s failed: %s", crawl_task_id, traceback.format_exc())
        return {"error": str(e)}


@celery_app.task
def check_crawl_timeouts():
    """Mark crawl tasks that have been running too long as failed.

    Tasks in 'crawling' or 'filtering' state for > 1 hour are timed out.
    """
    timeout_threshold = utcnow() - timedelta(hours=1)
    timed_out = CrawlTask.query.filter(
        CrawlTask.status.in_(["crawling", "filtering"]),
        CrawlTask.started_at < timeout_threshold,
    ).all()

    for t in timed_out:
        t.status = "failed"
        t.error_message = "Task timed out after 1 hour"
        t.completed_at = utcnow()
        logger.warning("CrawlTask %s timed out (started at %s)", t.id, t.started_at)

    if timed_out:
        db.session.commit()
        logger.info("Marked %d timed-out crawl tasks as failed", len(timed_out))

    return {"timed_out": len(timed_out)}


@celery_app.task
def schedule_due_crawls():
    """Find and execute crawl tasks that are due for their next run.

    Triggered by Celery Beat (see CELERY_BEAT_SCHEDULE in config).
    """
    now = utcnow()
    due = CrawlTask.query.filter(
        CrawlTask.schedule_interval > 0,
        CrawlTask.next_run_at <= now,
        CrawlTask.status.in_(["pending", "completed", "failed"]),
    ).all()

    launched = 0
    for t in due:
        try:
            run_crawl.delay(t.id)
            t.status = "pending"
            t.next_run_at = now + timedelta(minutes=t.schedule_interval)
            launched += 1
        except Exception as e:
            logger.error("Failed to launch scheduled crawl %s: %s", t.id, e)

    if due:
        db.session.commit()

    logger.info("Launched %d scheduled crawl tasks", launched)
    return {"launched": launched}
