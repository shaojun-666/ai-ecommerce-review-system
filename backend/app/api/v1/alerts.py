"""Alert API endpoints."""
from flask import request
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.api.v1 import api_bp
from app.services.alert_service import (
    get_alerts,
    mark_alert_read,
    mark_all_alerts_read,
    get_unread_count,
    run_all_checks,
)


@api_bp.route("/alerts", methods=["GET"])
@require_auth
def list_alerts(current_user):
    limit = request.args.get("limit", 50, type=int)
    limit = max(min(limit, 200), 1)
    unread_only = request.args.get("unread_only", "").lower() in ("1", "true", "yes")
    alerts = get_alerts(limit=limit, unread_only=unread_only)
    unread = get_unread_count()
    return success([a.to_dict() for a in alerts], meta={"unread": unread})


@api_bp.route("/alerts/<int:alert_id>/read", methods=["POST"])
@require_auth
def read_alert(current_user, alert_id):
    if mark_alert_read(alert_id):
        return success(message="Alert marked as read")
    return fail("Alert not found", 404)


@api_bp.route("/alerts/read-all", methods=["POST"])
@require_auth
def read_all_alerts(current_user):
    count = mark_all_alerts_read()
    return success({"marked_read": count})


@api_bp.route("/alerts/check", methods=["POST"])
@require_auth
def check_alerts(current_user):
    """Manually trigger all alert checks."""
    results = run_all_checks()
    total = sum(len(v) for v in results.values())
    return success({"created_total": total, "details": results})


@api_bp.route("/alerts/unread-count", methods=["GET"])
@require_auth
def unread_alert_count(current_user):
    return success({"unread": get_unread_count()})
