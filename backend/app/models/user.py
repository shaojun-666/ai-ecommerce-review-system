import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def utcnow():
    """Column-default-friendly wrapper for timezone-aware UTC now."""
    return datetime.datetime.now(datetime.timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # admin | user
    is_active = db.Column(db.Boolean, default=True)
    preferences = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    analysis_tasks = db.relationship("AnalysisTask", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "preferences": self.preferences or {},
            "created_at": self.created_at.isoformat(),
        }
