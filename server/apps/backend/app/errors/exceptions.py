from __future__ import annotations

from apps.backend.app.errors.codes import ErrorCode


class AppError(Exception):
    def __init__(self, code: ErrorCode, details: object = None, retry_after: int | None = None) -> None:
        self.code = code
        self.details = details
        self.retry_after = retry_after
        super().__init__(code.value)
