from __future__ import annotations

from apps.backend.app.errors.codes import ErrorCode


class AppError(Exception):
    def __init__(self, code: ErrorCode, details: object = None) -> None:
        self.code = code
        self.details = details
        super().__init__(code.value)
