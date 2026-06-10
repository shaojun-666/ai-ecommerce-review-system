from flask import request
from app.utils.auth import require_auth
from app.utils.response import success
from app.utils.cache import cache_get, cache_set, cache_delete_pattern
from app.services.analysis_service import (
    get_dashboard_overview,
    get_trend_data,
    get_keyword_rank,
    get_latest_comments,
)
from app.api.v1 import api_bp

# Cache TTLs (seconds)
OVERVIEW_CACHE_TTL = 300
TREND_CACHE_TTL = 600
KEYWORDS_CACHE_TTL = 600


@api_bp.route("/dashboard/overview", methods=["GET"])
@require_auth
def overview(current_user):
    cache_key = "dashboard:overview"

    cached = cache_get(cache_key)
    if cached is not None:
        return success(cached)

    data = get_dashboard_overview()
    cache_set(cache_key, data, ttl=OVERVIEW_CACHE_TTL)
    return success(data)


@api_bp.route("/dashboard/trend", methods=["GET"])
@require_auth
def trend(current_user):
    days = request.args.get("days", 30, type=int)
    days = min(max(days, 1), 365)
    cache_key = f"dashboard:trend:{days}"

    cached = cache_get(cache_key)
    if cached is not None:
        return success(cached)

    data = get_trend_data(days)
    cache_set(cache_key, data, ttl=TREND_CACHE_TTL)
    return success(data)


@api_bp.route("/dashboard/keywords", methods=["GET"])
@require_auth
def keywords(current_user):
    limit = request.args.get("limit", 30, type=int)
    limit = min(max(limit, 5), 100)
    cache_key = f"dashboard:keywords:{limit}"

    cached = cache_get(cache_key)
    if cached is not None:
        return success(cached)

    data = get_keyword_rank(limit)
    cache_set(cache_key, data, ttl=KEYWORDS_CACHE_TTL)
    return success(data)


@api_bp.route("/dashboard/latest-comments", methods=["GET"])
@require_auth
def latest_comments(current_user):
    limit = request.args.get("limit", 10, type=int)
    limit = min(max(limit, 5), 50)

    data = get_latest_comments(limit)
    return success(data)
