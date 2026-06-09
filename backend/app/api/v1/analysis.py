"""Analysis task API endpoints."""
from flask import request, jsonify
from app.api.v1 import api_bp
from app.utils.auth import require_auth
from app.extensions import db
from app.models.analysis_task import AnalysisTask
from app.models.comment import CommentAnalysis


@api_bp.route("/tasks", methods=["POST"])
@require_auth
def create_task(current_user):
    data = request.get_json() or {}
    name = data.get("name", f"Analysis_{current_user.id}")
    comment_ids = data.get("comment_ids", [])

    if not comment_ids:
        return jsonify({"error": "comment_ids required"}), 400

    task = AnalysisTask(
        user_id=current_user.id,
        name=name,
        status="pending",
        total_count=len(comment_ids),
    )
    db.session.add(task)
    db.session.commit()

    # Dispatch to Celery
    from app.tasks.analysis_tasks import run_analysis
    celery_task = run_analysis.delay(task.id, comment_ids)
    task.celery_task_id = celery_task.id
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@api_bp.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(current_user):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status = request.args.get("status")

    query = AnalysisTask.query.filter_by(user_id=current_user.id)
    if status:
        query = query.filter(AnalysisTask.status == status)

    query = query.order_by(AnalysisTask.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(current_user, task_id):
    task = AnalysisTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    return jsonify({"task": task.to_dict()})


@api_bp.route("/tasks/<int:task_id>/results", methods=["GET"])
@require_auth
def get_task_results(current_user, task_id):
    task = AnalysisTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = task.analyses.order_by(CommentAnalysis.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "items": [a.to_dict() for a in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "task_status": task.status,
    })
