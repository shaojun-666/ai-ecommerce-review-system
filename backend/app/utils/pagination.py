from flask import request


def paginate_query(query, page=None, per_page=None, max_per_page=100):
    try:
        page = int(page) if page else int(request.args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = int(per_page) if per_page else int(request.args.get("per_page", 20))
    except (ValueError, TypeError):
        per_page = 20

    page = max(page, 1)
    per_page = max(min(per_page, max_per_page), 1)

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total, page, per_page
