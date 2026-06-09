"""Comment management API endpoints."""
from flask import request, jsonify
from app.api.v1 import api_bp
from app.utils.auth import require_auth
from app.extensions import db
from app.models.comment import Comment


@api_bp.route("/comments", methods=["GET"])
@require_auth
def list_comments(current_user):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    product_id = request.args.get("product_id")
    platform = request.args.get("platform")
    sentiment = request.args.get("sentiment")

    query = Comment.query

    if product_id:
        query = query.filter(Comment.product_id == product_id)
    if platform:
        query = query.filter(Comment.platform == platform)

    # Join with analysis for sentiment filtering
    if sentiment:
        from app.models.comment import CommentAnalysis
        query = query.join(CommentAnalysis, Comment.id == CommentAnalysis.comment_id) \
                     .filter(CommentAnalysis.sentiment == sentiment)

    query = query.order_by(Comment.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })


@api_bp.route("/comments/<int:comment_id>", methods=["GET"])
@require_auth
def get_comment(current_user, comment_id):
    comment = Comment.query.get_or_404(comment_id)
    result = comment.to_dict()
    if comment.analysis:
        result["analysis"] = comment.analysis.to_dict()
    return jsonify(result)


@api_bp.route("/comments/batch", methods=["POST"])
@require_auth
def batch_import(current_user):
    """Import comments from CSV/JSON upload."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    from app.services.comment_service import import_comments_from_csv

    product_id = request.form.get("product_id", type=int)
    result = import_comments_from_csv(file, product_id=product_id, user_id=current_user.id)
    return jsonify({
        "message": f"Imported {result.imported} comments, skipped {result.skipped}",
        "imported": result.imported,
        "skipped": result.skipped,
        "errors": result.errors[:20],
    })


@api_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@require_auth
def delete_comment(current_user, comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Deleted"})
