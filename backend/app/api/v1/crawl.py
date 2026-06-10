"""CrawlTask CRUD API endpoints.

Provides:
    - GET    /crawl/tasks          — list crawl tasks (user's own or all for admin)
    - POST   /crawl/tasks          — create a new crawl task
    - GET    /crawl/tasks/<id>     — get crawl task details
    - POST   /crawl/tasks/<id>/start — manually start a crawl task
    - DELETE /crawl/tasks/<id>     — delete a crawl task
    - GET    /crawl/stats          — aggregated crawl statistics
"""
import logging
from datetime import datetime, timedelta

from flask import jsonify, request
from app.api.v1 import api_bp
from app.extensions import db
from app.models.crawl_task import CrawlTask
from app.models.product import Product
from app.tasks.crawl_tasks import run_crawl
from app.utils.auth import require_auth as jwt_required
from app.utils.pagination import paginate_query
from app.utils.response import success, fail
from app.utils.time import utcnow
from app.utils.validators import validate_url

logger = logging.getLogger(__name__)

JD_URL_WHITELIST = ("item.jd.com", "jd.com", "club.jd.com")


def _url_allowed(url: str) -> bool:
    """Validate URL against allowed domain whitelist.

    Rejects non-HTTPS URLs and URLs outside the JD.com domain family.
    """
    if not url.startswith("https://"):
        return False
    for domain in JD_URL_WHITELIST:
        if domain in url:
            return True
    return False


@api_bp.route("/crawl/tasks", methods=["GET"])
@jwt_required
def list_crawl_tasks(current_user):
    """List crawl tasks. Regular users see only their own tasks."""
    query = CrawlTask.query
    if current_user.role != "admin":
        query = query.filter_by(user_id=current_user.id)

    # Filters
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    platform = request.args.get("platform")
    if platform:
        query = query.filter_by(platform=platform)

    sort = request.args.get("sort", "-created_at")
    if sort == "created_at":
        query = query.order_by(CrawlTask.created_at.asc())
    elif sort == "-created_at":
        query = query.order_by(CrawlTask.created_at.desc())
    elif sort == "next_run_at":
        query = query.order_by(CrawlTask.next_run_at.asc().nullslast())
    else:
        query = query.order_by(CrawlTask.created_at.desc())

    items, total, page, per_page = paginate_query(query)
    return success(
        [t.to_dict() for t in items],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@api_bp.route("/crawl/tasks", methods=["POST"])
@jwt_required
def create_crawl_task(current_user):
    """Create a new crawl task."""
    data = request.get_json()
    if not data:
        return fail("Request body required")

    url = (data.get("url") or "").strip()
    if not url:
        return fail("URL is required")

    if not validate_url(url):
        return fail("Invalid URL format")

    if not _url_allowed(url):
        return fail("URL must be a valid JD.com HTTPS link (https://item.jd.com/...)")

    name = (data.get("name") or "").strip() or url
    platform = (data.get("platform") or "jd").strip().lower()
    if platform not in ("jd",):
        return fail(f"Unsupported platform: {platform}")

    page_limit = data.get("page_limit", 5)
    if not isinstance(page_limit, int) or page_limit < 1 or page_limit > 100:
        return fail("page_limit must be 1-100")

    schedule_interval = data.get("schedule_interval", 0)
    if not isinstance(schedule_interval, int) or schedule_interval < 0:
        return fail("schedule_interval must be >= 0")

    task = CrawlTask(
        user_id=current_user.id,
        name=name,
        platform=platform,
        url=url,
        page_limit=page_limit,
        schedule_interval=schedule_interval,
        next_run_at=(
            utcnow() + timedelta(minutes=schedule_interval)
            if schedule_interval > 0
            else None
        ),
    )
    db.session.add(task)
    db.session.commit()

    logger.info("CrawlTask %s created by user %s: %s", task.id, current_user.id, url)
    return success(task.to_dict(), 201)


@api_bp.route("/crawl/tasks/<int:task_id>", methods=["GET"])
@jwt_required
def get_crawl_task(current_user, task_id: int):
    """Get crawl task details."""
    task = db.session.get(CrawlTask, task_id)
    if not task:
        return fail("Crawl task not found", 404)

    if current_user.role != "admin" and task.user_id != current_user.id:
        return fail("Forbidden", 403)

    result = task.to_dict()
    if task.product_id:
        product = db.session.get(Product, task.product_id)
        if product:
            result["product"] = product.to_dict()

    return success(result)


@api_bp.route("/crawl/tasks/<int:task_id>/start", methods=["POST"])
@jwt_required
def start_crawl_task(current_user, task_id: int):
    """Manually trigger a crawl task."""
    task = db.session.get(CrawlTask, task_id)
    if not task:
        return fail("Crawl task not found", 404)

    if current_user.role != "admin" and task.user_id != current_user.id:
        return fail("Forbidden", 403)

    if not task.can_start():
        return fail(f"Task cannot be started (status={task.status})")

    run_crawl.delay(task.id)
    task.status = "pending"
    db.session.commit()

    logger.info("CrawlTask %s manually started by user %s", task_id, current_user.id)
    return success({"id": task.id, "status": "pending"})


@api_bp.route("/crawl/tasks/<int:task_id>", methods=["PUT"])
@jwt_required
def update_crawl_task(current_user, task_id: int):
    """Update crawl task configuration (only pending/failed tasks)."""
    task = db.session.get(CrawlTask, task_id)
    if not task:
        return fail("Crawl task not found", 404)

    if current_user.role != "admin" and task.user_id != current_user.id:
        return fail("Forbidden", 403)

    if task.is_running():
        return fail("Cannot update a running task")

    data = request.get_json() or {}
    if "name" in data:
        task.name = data["name"].strip() or task.name
    if "page_limit" in data:
        task.page_limit = max(1, min(100, int(data["page_limit"])))
    if "schedule_interval" in data:
        task.schedule_interval = max(0, int(data["schedule_interval"]))
        if task.schedule_interval > 0:
            task.next_run_at = utcnow() + timedelta(minutes=task.schedule_interval)

    db.session.commit()
    return success(task.to_dict())


@api_bp.route("/crawl/tasks/<int:task_id>", methods=["DELETE"])
@jwt_required
def delete_crawl_task(current_user, task_id: int):
    """Delete a crawl task."""
    task = db.session.get(CrawlTask, task_id)
    if not task:
        return fail("Crawl task not found", 404)

    if current_user.role != "admin" and task.user_id != current_user.id:
        return fail("Forbidden", 403)

    db.session.delete(task)
    db.session.commit()
    return success({"deleted": True})


@api_bp.route("/crawl/stats", methods=["GET"])
@jwt_required
def crawl_stats(current_user):
    """Aggregated crawl statistics."""
    query = CrawlTask.query
    if current_user.role != "admin":
        query = query.filter_by(user_id=current_user.id)

    total = query.count()
    running = query.filter(CrawlTask.status.in_(["crawling", "filtering"])).count()
    completed = query.filter_by(status="completed").count()
    failed = query.filter_by(status="failed").count()
    pending = query.filter_by(status="pending").count()

    # Total items collected
    total_items = db.session.query(
        db.func.coalesce(db.func.sum(CrawlTask.items_new), 0)
    ).filter(
        CrawlTask.status == "completed"
    ).scalar()

    return success({
        "total": total,
        "running": running,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "total_items_collected": total_items,
    })
