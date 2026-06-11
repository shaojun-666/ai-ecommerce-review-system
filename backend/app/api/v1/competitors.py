"""Competitor discovery API endpoints."""
from flask import request
from app.utils.auth import require_auth
from app.utils.response import success
from app.api.v1 import api_bp
from app.services.competitor_service import discover_competitors, get_competitor_summary


@api_bp.route("/competitors", methods=["GET"])
@require_auth
def list_competitors(current_user):
    product_id = request.args.get("product_id", type=int)
    min_overlap = request.args.get("min_overlap", 1, type=int)
    data = discover_competitors(product_id=product_id, min_tag_overlap=min_overlap)
    return success(data)


@api_bp.route("/competitors/summary", methods=["GET"])
@require_auth
def competitor_summary(current_user):
    data = get_competitor_summary()
    return success(data)
