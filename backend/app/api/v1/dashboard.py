from flask import request
from app.utils.auth import require_auth
from app.utils.response import success
from app.services.analysis_service import get_dashboard_overview, get_trend_data, get_keyword_rank
from app.api.v1 import api_bp


@api_bp.route("/dashboard/overview", methods=["GET"])
@require_auth
def overview(current_user):
    data = get_dashboard_overview()
    return success(data)


@api_bp.route("/dashboard/trend", methods=["GET"])
@require_auth
def trend(current_user):
    days = request.args.get("days", 30, type=int)
    days = min(max(days, 1), 365)
    data = get_trend_data(days)
    return success(data)


@api_bp.route("/dashboard/keywords", methods=["GET"])
@require_auth
def keywords(current_user):
    limit = request.args.get("limit", 30, type=int)
    limit = min(max(limit, 5), 100)
    data = get_keyword_rank(limit)
    return success(data)
