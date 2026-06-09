from flask import Response, request
from app.utils.auth import require_auth
from app.utils.response import success, fail
from app.services.report_service import generate_excel_report, generate_summary_report
from app.services.analysis_service import get_dashboard_overview, get_trend_data, get_keyword_rank
from app.api.v1 import api_bp


@api_bp.route("/reports/export/<int:task_id>", methods=["GET"])
@require_auth
def export_report(current_user, task_id):
    fmt = request.args.get("format", "csv")
    if fmt != "csv":
        return fail("Only CSV format is supported", 400)

    csv_data = generate_excel_report(task_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_report_{task_id}.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@api_bp.route("/reports/summary", methods=["GET"])
@require_auth
def export_summary(current_user):
    overview = get_dashboard_overview()
    trend = get_trend_data(30)
    keywords = get_keyword_rank(20)
    csv_data = generate_summary_report(overview, trend, keywords)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=summary_report.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )
