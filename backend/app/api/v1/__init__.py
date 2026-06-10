from flask import Blueprint

api_bp = Blueprint("api_v1", __name__)

from app.api.v1 import auth, comments, analysis, users, dashboard, reports, products  # noqa: E402, F401
from app.api.v1 import crawl  # noqa: E402, F401
