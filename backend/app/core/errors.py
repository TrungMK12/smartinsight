"""Lỗi nghiệp vụ dùng chung, được map ra HTTP response nhất quán."""

from __future__ import annotations


class AppError(Exception):
    status_code: int = 400
    error_code: str = "app_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BadRequestError(AppError):
    status_code = 400
    error_code = "bad_request"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "unauthorized"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class DuplicateError(AppError):
    status_code = 409
    error_code = "duplicate"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "service_unavailable"
