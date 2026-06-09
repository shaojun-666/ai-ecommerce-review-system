from flask import jsonify


def success(data=None, message="success", code=200, meta=None):
    body = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), code


def fail(message="error", code=400, data=None):
    body = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), code


def paginated_data(items, total, page, per_page):
    return {
        "data": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if total else 0,
        },
    }
