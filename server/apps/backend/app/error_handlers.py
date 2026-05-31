from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.backend.app.errors.codes import ERROR_META, ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.services.storage.base import StorageError

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).parent / "errors" / "locales"

_LOCALES: dict[str, dict[str, str]] = {
    "zh-CN": json.loads((_LOCALES_DIR / "zh-CN.json").read_text(encoding="utf-8")),
    "en-US": json.loads((_LOCALES_DIR / "en-US.json").read_text(encoding="utf-8")),
}

_VALIDATION_CODE_MAP = {
    "missing": "REQUIRED",
    "string_too_short": "TOO_SHORT",
    "string_too_long": "TOO_LONG",
    "value_error": "INVALID_VALUE",
    "string_pattern_mismatch": "INVALID_FORMAT",
    "int_type": "INVALID_TYPE",
    "float_type": "INVALID_TYPE",
    "string_type": "INVALID_TYPE",
    "bool_type": "INVALID_TYPE",
    "int_parsing_error": "INVALID_TYPE",
    "int_parsing": "INVALID_TYPE",
    "float_parsing_error": "INVALID_TYPE",
    "float_parsing": "INVALID_TYPE",
    "greater_than": "INVALID_VALUE",
    "greater_than_equal": "INVALID_VALUE",
    "less_than": "INVALID_VALUE",
    "less_than_equal": "INVALID_VALUE",
    "enum": "INVALID_VALUE",
    "url_type": "INVALID_FORMAT",
    "datetime_type": "INVALID_FORMAT",
}


def _parse_lang(request: Request) -> str:
    header = request.headers.get("accept-language", "")
    for part in header.split(","):
        tag = part.strip().split(";")[0].strip()
        lang = tag.split("-")[0].lower()
        if lang == "zh":
            return "zh-CN"
        if lang == "en":
            return "en-US"
    return "zh-CN"


def _get_message(code: str, lang: str) -> str:
    messages = _LOCALES.get(lang, _LOCALES["zh-CN"])
    return messages.get(code, code)


def _error_envelope(code: str, message: str, request_id: str, details=None) -> dict:
    env: dict = {"code": code, "message": message, "data": None, "request_id": request_id}
    if details is not None:
        env["details"] = details
    return env


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    lang = _parse_lang(request)
    message = _get_message(exc.code.value, lang)
    request_id = getattr(request.state, "request_id", "unknown")
    user_id = getattr(request.state, "user_id", "anonymous")
    logger.warning(
        f"AppError: error_code={exc.code.value} path={request.url.path} "
        f"method={request.method} request_id={request_id} user_id={user_id}"
    )
    headers: dict[str, str] | None = None
    if exc.retry_after is not None:
        headers = {"Retry-After": str(exc.retry_after)}
    return JSONResponse(
        status_code=ERROR_META[exc.code],
        content=_error_envelope(exc.code.value, message, request_id, exc.details),
        headers=headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    lang = _parse_lang(request)
    request_id = getattr(request.state, "request_id", "unknown")
    details = []
    for error in exc.errors():
        pydantic_type = error.get("type", "")
        code = _VALIDATION_CODE_MAP.get(pydantic_type, "INVALID_VALUE")
        field = str(error["loc"][-1]) if error.get("loc") else "unknown"
        ctx = error.get("ctx", {})
        if code == "TOO_SHORT" and "min_length" in ctx:
            template = _get_message("VALIDATION_TOO_SHORT", lang)
            msg = template.format(min_length=ctx["min_length"])
        elif code == "TOO_LONG" and "max_length" in ctx:
            template = _get_message("VALIDATION_TOO_LONG", lang)
            msg = template.format(max_length=ctx["max_length"])
        elif pydantic_type == "value_error":
            # Use the ValueError message directly (e.g. "密码必须包含大写字母")
            raw = error.get("msg", "")
            msg = raw.removeprefix("Value error, ") if raw else _get_message("VALIDATION_INVALID_VALUE", lang)
        else:
            locale_key = f"VALIDATION_{code}"
            locale_msg = _get_message(locale_key, lang)
            msg = locale_msg if locale_msg != locale_key else error.get("msg", code)
        details.append({"field": field, "code": code, "msg": msg})
    message = _get_message("VALIDATION_ERROR", lang)
    return JSONResponse(
        status_code=422,
        content=_error_envelope("VALIDATION_ERROR", message, request_id, details),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    lang = _parse_lang(request)
    request_id = getattr(request.state, "request_id", "unknown")
    code_map = {401: "AUTH_TOKEN_EXPIRED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "FORBIDDEN", 500: "INTERNAL_ERROR"}
    error_code = code_map.get(exc.status_code, "INTERNAL_ERROR")
    message = _get_message(error_code, lang)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(error_code, message, request_id),
    )


async def storage_error_handler(request: Request, exc: StorageError) -> JSONResponse:
    from apps.backend.app.services.storage.base import (
        StorageAuthError,
        StorageConflictError,
        StorageConnectionError,
        StorageRateLimitError,
    )

    lang = _parse_lang(request)
    request_id = getattr(request.state, "request_id", "unknown")
    if isinstance(exc, StorageRateLimitError):
        error_code = ErrorCode.STORAGE_RATE_LIMITED
        details = {"reset_at": exc.reset_at} if exc.reset_at is not None else None
    elif isinstance(exc, StorageConflictError):
        error_code = ErrorCode.STORAGE_CONFLICT
        details = None
    elif isinstance(exc, StorageConnectionError):
        error_code = ErrorCode.STORAGE_CONNECTION_ERROR
        details = None
    elif isinstance(exc, StorageAuthError):
        error_code = ErrorCode.STORAGE_AUTH_ERROR
        details = None
    else:
        error_code = ErrorCode.STORAGE_ERROR
        details = None
    message = _get_message(error_code.value, lang)
    user_id = getattr(request.state, "user_id", "anonymous")
    logger.warning(
        f"StorageError: error_code={error_code.value} path={request.url.path} "
        f"method={request.method} request_id={request_id} user_id={user_id}"
    )
    return JSONResponse(
        status_code=ERROR_META[error_code],
        content=_error_envelope(error_code.value, message, request_id, details),
    )
