"""SocketIO event handlers for real-time updates."""
import logging
from flask import request
from app.extensions import socketio, db
from app.models.alert import Alert
from app.services.alert_service import get_unread_count as alert_unread_count

logger = logging.getLogger(__name__)


@socketio.on("connect", namespace="/ws")
def handle_connect():
    logger.info("Client connected: %s", request.sid)
    return True


@socketio.on("disconnect", namespace="/ws")
def handle_disconnect():
    logger.info("Client disconnected: %s", request.sid)


@socketio.on("ping", namespace="/ws")
def handle_ping():
    return {"status": "pong"}


def broadcast_dashboard_update(data: dict):
    """Broadcast dashboard refresh data to all connected clients."""
    socketio.emit("dashboard_update", data, namespace="/ws")


def broadcast_alert_notification(alert_data: dict):
    """Push a new alert notification to all connected clients."""
    unread = alert_unread_count()
    socketio.emit("new_alert", {**alert_data, "unread": unread}, namespace="/ws")


def broadcast_alert_count_update():
    """Broadcast updated unread alert count."""
    unread = alert_unread_count()
    socketio.emit("alert_count", {"unread": unread}, namespace="/ws")
