"""CrawlTask CRUD + Auto-Crawl + Discovery + Export API endpoints.

Provides:
    - CRUD:        GET/POST /crawl/tasks, GET/PUT/DELETE /crawl/tasks/<id>
    - Control:     POST /crawl/tasks/<id>/start
    - Stats:       GET /crawl/stats
    - Auto-Crawl:  POST /crawl/auto/start, POST /crawl/auto/stop, GET /crawl/auto/status
    - Discovery:   GET /crawl/discovery/categories
    - Export:      GET /crawl/exports, POST /crawl/exports/export
"""
import logging
from datetime import timedelta

from flask import request
from app.api.v1 import api_bp
from app.extensions import db
from app.models.crawl_task import CrawlTask
from app.models.product import Product
from app.services.crawl_state import start_session, stop_session, get_session
from app.utils.auth import require_auth as jwt_required
from app.utils.pagination import paginate_query
from app.utils.response import success, fail
from app.utils.time import utcnow
from app.utils.validators import validate_url

logger = logging.getLogger(__name__)

JD_URL_WHITELIST = ("item.jd.com", "jd.com", "club.jd.com")


def _url_allowed(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    for domain in JD_URL_WHITELIST:
        if domain in url:
            return True
    return False


# ═════════════════════════════════════════════════════════════════════
#  Existing CRUD Endpoints (unchanged)
# ═════════════════════════════════════════════════════════════════════

@api_bp.route("/crawl/tasks", methods=["GET"])
@jwt_required
def list_crawl_tasks(current_user):
    """List crawl tasks."""
    query = CrawlTask.query
    if current_user.role != "admin":
        query = query.filter_by(user_id=current_user.id)

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    platform = request.args.get("platform")
    if platform:
        query = query.filter_by(platform=platform)

    sort = request.args.get("sort", "-created_at")
    sort_map = {
        "created_at": CrawlTask.created_at.asc(),
        "-created_at": CrawlTask.created_at.desc(),
        "next_run_at": CrawlTask.next_run_at.asc().nullslast(),
    }
    query = query.order_by(sort_map.get(sort, CrawlTask.created_at.desc()))

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
        return fail("URL must be a valid JD.com HTTPS link")

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
            if schedule_interval > 0 else None
        ),
    )
    db.session.add(task)
    db.session.commit()

    logger.info("CrawlTask %s created by user %s: %s", task.id, current_user.id, url)
    return success(task.to_dict(), 201)


@api_bp.route("/crawl/tasks/<int:task_id>", methods=["GET"])
@jwt_required
def get_crawl_task(current_user, task_id: int):
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
    task = db.session.get(CrawlTask, task_id)
    if not task:
        return fail("Crawl task not found", 404)
    if current_user.role != "admin" and task.user_id != current_user.id:
        return fail("Forbidden", 403)
    if not task.can_start():
        return fail(f"Task cannot be started (status={task.status})")

    from app.tasks.crawl_tasks import run_crawl
    run_crawl.delay(task.id)
    task.status = "pending"
    db.session.commit()

    logger.info("CrawlTask %s manually started by user %s", task_id, current_user.id)
    return success({"id": task.id, "status": "pending"})


@api_bp.route("/crawl/tasks/<int:task_id>", methods=["PUT"])
@jwt_required
def update_crawl_task(current_user, task_id: int):
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

    total_items = db.session.query(
        db.func.coalesce(db.func.sum(CrawlTask.items_new), 0)
    ).filter(CrawlTask.status == "completed").scalar()

    # Auto-crawl session info
    sess = get_session()
    session_info = {
        "auto_running": sess["running"],
        "auto_started_at": sess["started_at"],
        "auto_platforms": sess["platforms"],
        "auto_stats": dict(sess["stats"]),
    }

    return success({
        "total": total,
        "running": running,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "total_items_collected": total_items,
        **session_info,
    })


# ═════════════════════════════════════════════════════════════════════
#  NEW: Auto-Crawl Session Endpoints
# ═════════════════════════════════════════════════════════════════════

@api_bp.route("/crawl/auto/start", methods=["POST"])
@jwt_required
def auto_crawl_start(current_user):
    """Start an auto-crawl session.

    Body (JSON):
        platforms:       list of platforms (default: all)  e.g. ["jd","taobao"]
        max_per_category: max products per category (default: 20)
        page_limit:       review pages per task (default: 3)
        interval_minutes: minutes between discovery runs (default: 30)
    """
    data = request.get_json() or {}

    sess = get_session()
    if sess["running"]:
        return fail("Auto-crawl session is already running. Stop it first.", 409)

    platforms = data.get("platforms")
    if platforms is not None:
        valid = {"jd", "taobao", "pdd"}
        unknown = set(platforms) - valid
        if unknown:
            return fail(f"Unsupported platforms: {unknown}. Valid: {valid}")

    max_per = max(5, min(50, data.get("max_per_category", 20)))
    p_limit = max(1, min(20, data.get("page_limit", 3)))
    interval = max(10, min(240, data.get("interval_minutes", 30)))

    start_session(platforms=platforms, max_per_category=max_per,
                  page_limit=p_limit, interval_minutes=interval)

    # Launch the auto-crawl Celery task
    from app.tasks.crawl_tasks import run_auto_discovery
    run_auto_discovery.delay(current_user.id)

    logger.info("Auto-crawl session started by user %s", current_user.id)
    return success({
        "message": "Auto-crawl session started",
        "session": get_session(),
    })


@api_bp.route("/crawl/auto/stop", methods=["POST"])
@jwt_required
def auto_crawl_stop(current_user):
    """Stop the current auto-crawl session."""
    sess = get_session()
    was_running = sess["running"]
    stop_session()

    if was_running:
        logger.info("Auto-crawl session stopped by user %s", current_user.id)
        return success({"message": "Auto-crawl session stopped", "was_running": True})
    return success({"message": "No active auto-crawl session", "was_running": False})


@api_bp.route("/crawl/auto/status", methods=["GET"])
@jwt_required
def auto_crawl_status(_current_user):
    """Get current auto-crawl session status."""
    return success(get_session())


# ═════════════════════════════════════════════════════════════════════
#  NEW: Discovery Endpoints
# ═════════════════════════════════════════════════════════════════════

@api_bp.route("/crawl/discovery/categories", methods=["GET"])
@jwt_required
def discovery_categories(_current_user):
    """List all available seed categories for auto-discovery."""
    from app.services.crawl_discovery import CrawlDiscoveryService
    service = CrawlDiscoveryService()
    cats = service.get_available_categories()
    return success(cats)


@api_bp.route("/crawl/discovery/discover", methods=["POST"])
@jwt_required
def discovery_manual_discover(current_user):
    """Manually trigger a one-shot discovery run.

    Body:
        platforms: list of platforms (default: all)
        max_per_category: max products (default: 20)
        auto_start: whether to crawl discovered products immediately (default: true)
        page_limit: review pages per task (default: 3)
    """
    data = request.get_json() or {}
    platforms = data.get("platforms")
    max_per = data.get("max_per_category", 20)
    auto_start = data.get("auto_start", True)
    page_limit = data.get("page_limit", 3)

    from app.services.crawl_discovery import CrawlDiscoveryService
    service = CrawlDiscoveryService()
    stats = service.discover_and_create_tasks(
        user_id=current_user.id,
        platforms=platforms,
        max_per_category=max_per,
        auto_start=auto_start,
        page_limit=page_limit,
    )

    return success(stats.to_dict())


# ═════════════════════════════════════════════════════════════════════
#  NEW: Data Export Endpoints
# ═════════════════════════════════════════════════════════════════════

@api_bp.route("/crawl/exports", methods=["GET"])
@jwt_required
def list_exports(_current_user):
    """List previous data exports."""
    from app.services.data_exporter import DataExporter
    exporter = DataExporter()
    exports = exporter.list_exports(limit=20)
    return success(exports)


@api_bp.route("/crawl/exports/export", methods=["POST"])
@jwt_required
def trigger_export(_current_user):
    """Manually trigger a data export.

    Body:
        platforms: list of platforms (default: all)
    """
    data = request.get_json() or {}
    platforms = data.get("platforms")

    from app.services.data_exporter import DataExporter, set_last_export_count
    from app.models.comment import Comment

    exporter = DataExporter()
    manifest = exporter.export_all(platforms=platforms)

    # Update last export count
    current_count = Comment.query.count()
    set_last_export_count(current_count)

    logger.info("Manual export triggered by user: %s", manifest.to_dict())
    return success(manifest.to_dict())


@api_bp.route("/crawl/exports/latest", methods=["GET"])
@jwt_required
def get_latest_export(_current_user):
    """Get the latest export directory listing."""
    from app.services.data_exporter import DataExporter, DEFAULT_EXPORT_DIR
    import os

    exporter = DataExporter()
    exports = exporter.list_exports(limit=1)
    if not exports:
        return success(None)

    latest = exports[0]
    export_path = latest.get("export_dir", "")
    # List files in the latest export
    files = []
    if os.path.isdir(export_path):
        for root, _dirs, filenames in os.walk(export_path):
            for fn in filenames:
                if fn.endswith(".json"):
                    rel = os.path.relpath(os.path.join(root, fn), export_path)
                    fpath = os.path.join(root, fn)
                    files.append({
                        "path": rel,
                        "size": os.path.getsize(fpath),
                    })

    return success({
        "manifest": latest,
        "files": files,
        "export_path": export_path,
    })


@api_bp.route("/crawl/exports/download", methods=["GET"])
@jwt_required
def download_export_file(_current_user):
    """Download a specific export file by path.

    Query params:
        path: relative file path within the export directory
              e.g. "2026-06-13_143022/jd/products.json"
    """
    from app.services.data_exporter import DEFAULT_EXPORT_DIR
    import os

    rel_path = request.args.get("path", "")
    if not rel_path:
        return fail("path parameter is required")

    # Security: prevent path traversal
    norm = os.path.normpath(rel_path)
    if norm.startswith("..") or os.path.isabs(norm):
        return fail("Invalid path")
    if not norm.endswith(".json"):
        return fail("Only .json files can be downloaded")

    full_path = os.path.join(DEFAULT_EXPORT_DIR, norm)
    if not os.path.isfile(full_path):
        return fail("File not found", 404)

    from flask import send_file
    return send_file(full_path, mimetype="application/json", as_attachment=True,
                     download_name=os.path.basename(full_path))
