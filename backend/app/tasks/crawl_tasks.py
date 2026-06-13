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
from app.models.product_price import ProductPrice
from app.crawler.adapters import get_crawler
from app.services.data_pipeline import DataPipeline
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
        # Select crawler based on platform via registry
        crawler = get_crawler(task.platform)

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
                platform=task.platform,
                platform_product_id=platform_id,
            ).first() if platform_id else None

            if not product:
                product = Product(
                    name=result.product.get("name", task.name),
                    platform=task.platform,
                    platform_product_id=platform_id or "",
                    user_id=task.user_id,
                )
                db.session.add(product)
                db.session.flush()

            # Update task product link
            task.product_id = product.id

            # Record price snapshot
            price = result.product.get("price")
            if price is not None:
                try:
                    db.session.add(ProductPrice(
                        product_id=product.id,
                        price=float(price),
                        platform=task.platform,
                        source="crawl",
                    ))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.warning("Failed to record price snapshot: %s", e)

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
                                platform=pr.platform or task.platform,
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

        # Update last_crawled_at and invalidate dashboard cache
        if product:
            DataPipeline.mark_crawled(product.id)

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


@celery_app.task
def snapshot_prices():
    """Record current prices for all products that have a crawl task configured.

    This is triggered by Celery Beat (e.g., every 6 hours) to build
    price history even when no new crawl is actively running.
    """
    from app.crawler.adapters import get_crawler as get_crawler_factory

    products = Product.query.filter(Product.url != "", Product.platform != "").all()
    recorded = 0
    failed = 0

    for product in products:
        try:
            crawler = get_crawler_factory(product.platform)
            result = crawler.crawl_product(product.url)
            if result.product and result.product.get("price") is not None:
                db.session.add(ProductPrice(
                    product_id=product.id,
                    price=float(result.product["price"]),
                    platform=product.platform,
                    source="crawl",
                ))
                recorded += 1
            else:
                logger.debug("No price found for product %s", product.id)
        except Exception as e:
            failed += 1
            logger.warning("Price snapshot failed for product %s: %s", product.id, e)

    if recorded or failed:
        db.session.commit()
        logger.info("Price snapshot: %d recorded, %d failed", recorded, failed)

    return {"recorded": recorded, "failed": failed}


# ═════════════════════════════════════════════════════════════════════
#  Auto-Discovery Tasks
# ═════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def run_auto_discovery(self, user_id: int):
    """Run one cycle of auto-discovery, then reschedule if session is active.

    Launched by POST /crawl/auto/start. Each cycle:
        1. Discovers products from configured categories
        2. Creates crawl tasks for new discoveries
        3. Checks if auto-export is needed
        4. Reschedules itself if the session is still active
    """
    from app.services.crawl_state import get_session, update_stats

    sess = get_session()
    if not sess["running"]:
        logger.info("Auto-discovery: session not active, skipping cycle")
        return {"status": "skipped", "reason": "session not active"}

    platforms = sess["platforms"]
    max_per = sess["max_per_category"]
    page_limit = sess["page_limit"]
    interval = sess["interval_minutes"]

    logger.info(
        "Auto-discovery cycle starting (platforms=%s, max_per=%d, page_limit=%d)",
        platforms or "all", max_per, page_limit,
    )

    stats_dict = {}
    # ── Discover ──
    try:
        from app.services.crawl_discovery import CrawlDiscoveryService
        service = CrawlDiscoveryService()
        stats = service.discover_and_create_tasks(
            user_id=user_id,
            platforms=platforms,
            max_per_category=max_per,
            auto_start=True,
            page_limit=page_limit,
        )
        stats_dict = stats.to_dict()
        logger.info("Auto-discovery cycle complete: %s", stats_dict)

        update_stats(
            discovery_runs=1,
            total_products_found=stats.products_found,
            total_tasks_created=stats.tasks_created,
        )

    except Exception as e:
        logger.error("Auto-discovery cycle failed: %s", e, exc_info=True)

    # ── Auto-export ──
    try:
        from app.services.data_exporter import DataExporter, set_last_export_count
        from app.models.comment import Comment
        exporter = DataExporter()
        manifest = exporter.check_and_auto_export(threshold=500)
        if manifest:
            logger.info("Auto-export triggered: %s", manifest.to_dict())
            update_stats(total_exports=1)
            current_count = Comment.query.count()
            set_last_export_count(current_count)
    except Exception as e:
        logger.warning("Auto-export check failed: %s", e)

    # ── Reschedule ──
    import time
    time.sleep(2)  # allow stop signal to arrive

    sess = get_session()
    if sess["running"]:
        countdown = interval * 60
        run_auto_discovery.apply_async(args=[user_id], countdown=countdown)
        logger.info("Auto-discovery next cycle scheduled in %d minutes", interval)
    else:
        logger.info("Auto-discovery session ended, no reschedule")

    return {
        "status": "completed" if sess["running"] else "stopped",
        "stats": stats_dict,
    }
