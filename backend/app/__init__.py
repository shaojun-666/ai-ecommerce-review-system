"""App factory for AI E-commerce Review Analysis System."""
from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.extensions import db, migrate, init_redis
from app.config import get_config


limiter = Limiter(key_func=get_remote_address)


def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, supports_credentials=True, origins=app.config.get("CORS_ORIGINS", "*"))
    limiter.init_app(app)

    # Initialize Redis
    init_redis(app)

    # Register blueprints
    from app.api.v1 import api_bp
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Register error handlers
    from app.utils.errors import register_error_handlers
    register_error_handlers(app)

    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    return app
