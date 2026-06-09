from flask import current_app
from .response import fail


class AppException(Exception):
    def __init__(self, message, code=400, status_code=None):
        self.message = message
        self.code = code
        self.status_code = status_code or code
        super().__init__(self.message)


class BadRequest(AppException):
    def __init__(self, message="Bad request"):
        super().__init__(message, code=400, status_code=400)


class Unauthorized(AppException):
    def __init__(self, message="Unauthorized"):
        super().__init__(message, code=401, status_code=401)


class Forbidden(AppException):
    def __init__(self, message="Forbidden"):
        super().__init__(message, code=403, status_code=403)


class NotFound(AppException):
    def __init__(self, message="Resource not found"):
        super().__init__(message, code=404, status_code=404)


class Unprocessable(AppException):
    def __init__(self, message="Unprocessable entity"):
        super().__init__(message, code=422, status_code=422)


class TooManyRequests(AppException):
    def __init__(self, message="Too many requests"):
        super().__init__(message, code=429, status_code=429)


def register_error_handlers(app):
    @app.errorhandler(400)
    def handle_400(e):
        return fail("Bad request", 400)

    @app.errorhandler(401)
    def handle_401(e):
        return fail("Unauthorized", 401)

    @app.errorhandler(403)
    def handle_403(e):
        return fail("Forbidden", 403)

    @app.errorhandler(404)
    def handle_404(e):
        return fail("Resource not found", 404)

    @app.errorhandler(422)
    def handle_422(e):
        return fail("Unprocessable entity", 422)

    @app.errorhandler(429)
    def handle_429(e):
        return fail("Too many requests", 429)

    @app.errorhandler(500)
    def handle_500(e):
        current_app.logger.exception("Internal server error")
        return fail("Internal server error", 500)

    @app.errorhandler(AppException)
    def handle_app_exception(e):
        return fail(e.message, e.code)
