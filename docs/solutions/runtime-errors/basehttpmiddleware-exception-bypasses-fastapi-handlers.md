---
title: "BaseHTTPMiddleware exceptions bypass FastAPI exception handlers — returns 500 instead of proper error code"
date: "2026-08-20"
category: runtime-errors
module: server/apps/backend
problem_type: runtime_error
component: service_object
severity: high
symptoms:
  - "Rate limit exceeded returns HTTP 500 instead of 429 with Retry-After header"
  - "AppError raised inside BaseHTTPMiddleware.dispatch() is caught by Starlette catch-all, not FastAPI's add_exception_handler()"
  - "i18n error envelope lost — frontend sees generic Internal Server Error"
root_cause: wrong_api
resolution_type: code_fix
tags:
  - fastapi
  - basehttpmiddleware
  - starlette
  - exception-handling
  - rate-limit
  - error-envelope
---

# BaseHTTPMiddleware Exceptions Bypass FastAPI Exception Handlers

## Problem

`RateLimitMiddleware` (a `BaseHTTPMiddleware` subclass) raised `AppError(ErrorCode.RATE_LIMITED)` when a client exceeded the rate limit. FastAPI's `add_exception_handler(AppError, ...)` was registered, but the middleware still returned HTTP 500. The root cause: Starlette's `BaseHTTPMiddleware` wraps `dispatch()` in a try/except that catches all exceptions before they reach FastAPI's exception handler registry.

## Symptoms

- Rate-limited requests return HTTP 500 with a generic `{"detail": "Internal Server Error"}` body.
- The proper 429 response (with i18n envelope and `Retry-After` header) never reaches the client.
- Other `AppError` raises in routers and services work correctly — only those inside `BaseHTTPMiddleware.dispatch()` are affected.

## What Didn't Work

- Adding another `add_exception_handler(AppError, ...)` — already registered, the issue is that Starlette's middleware wrapper intercepts before the handler runs.
- Raising `HTTPException` directly — loses the i18n envelope and `Retry-After` header logic encapsulated in `app_error_handler()`.

## Solution

Call `app_error_handler()` directly inside `dispatch()` instead of raising:

```python
# ❌ Wrong — exception is caught by Starlette's catch-all → 500
raise AppError(ErrorCode.RATE_LIMITED)

# ✅ Correct — call the handler directly, return its Response
from apps.backend.app.error_handlers import app_error_handler

if not self._check_rate_limit(client_id):
    return await app_error_handler(request, AppError(ErrorCode.RATE_LIMITED))
```

The `app_error_handler()` function returns a `JSONResponse` with the proper status code (429), i18n error envelope, and `Retry-After` header.

## Why This Works

`BaseHTTPMiddleware.dispatch()` runs inside Starlette's middleware stack, which wraps exceptions in its own error handling before they propagate to FastAPI's exception handler registry. By calling `app_error_handler()` directly and returning its `Response`, we bypass the exception propagation entirely and produce the correct HTTP response at the middleware level.

This is a well-known Starlette/FastAPI footgun: exceptions raised in `BaseHTTPMiddleware` subclasses do NOT go through `app.add_exception_handler()`. See [encode/starlette#1933](https://github.com/encode/starlette/issues/1933).

## Prevention

- **Rule:** Never `raise` custom exceptions inside `BaseHTTPMiddleware.dispatch()`. Always call the error handler directly and return the response.
- **Alternative:** Use pure ASGI middleware (not `BaseHTTPMiddleware`) which doesn't have this exception-swallowing behavior, but at the cost of a more complex API.
- **Test:** Add an integration test that hits the rate limit and asserts the response status code is 429, not 500.

## Related Issues

- Related: `docs/solutions/integration-issues/production-deployment-config-mismatches.md` (other production deployment issues)
