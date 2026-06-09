"""Timezone-aware UTC datetime utilities."""
import datetime


def utcnow() -> datetime.datetime:
    """Return current UTC datetime (timezone-aware).

    Use this instead of deprecated ``datetime.datetime.utcnow()``.
    For SQLAlchemy column defaults, pass the function reference ``utcnow``
    (without calling it) so SQLAlchemy invokes it at row-creation time.
    """
    return datetime.datetime.now(datetime.UTC)
