"""Shared auto-crawl session state — avoids circular imports between crawl.py and crawl_tasks.py."""
import threading
from datetime import datetime, timezone

# Auto-crawl session state
auto_session = {
    "running": False,
    "platforms": None,
    "max_per_category": 20,
    "page_limit": 3,
    "interval_minutes": 30,
    "started_at": None,
    "stats": {
        "discovery_runs": 0,
        "total_products_found": 0,
        "total_tasks_created": 0,
        "total_exports": 0,
    },
}

session_lock = threading.Lock()


def reset_session():
    with session_lock:
        auto_session["running"] = False
        auto_session["started_at"] = None


def start_session(platforms=None, max_per_category=20, page_limit=3, interval_minutes=30):
    with session_lock:
        auto_session["running"] = True
        auto_session["platforms"] = platforms
        auto_session["max_per_category"] = max_per_category
        auto_session["page_limit"] = page_limit
        auto_session["interval_minutes"] = interval_minutes
        auto_session["started_at"] = datetime.now(timezone.utc).isoformat()


def stop_session():
    with session_lock:
        auto_session["running"] = False


def get_session():
    with session_lock:
        return dict(auto_session)


def update_stats(**kwargs):
    with session_lock:
        for k, v in kwargs.items():
            if k in auto_session["stats"]:
                auto_session["stats"][k] += v
