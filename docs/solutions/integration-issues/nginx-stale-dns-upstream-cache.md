---
title: Nginx Stale DNS Cache Causes 502 on ALTCHA Captcha Endpoint
date: 2026-08-01
category: integration-issues
module: authentication
problem_type: integration_issue
component: authentication
severity: high
symptoms:
  - "502 Bad Gateway on /api/v1/captcha/challenge"
  - Login blocked due to captcha failure
  - ALTCHA widget shows error state
root_cause: config_error
resolution_type: config_change
tags:
  - nginx
  - docker
  - dns-cache
  - upstream
  - altcha
  - captcha
  - 502
  - container-rebuild
---

# Nginx Stale DNS Cache Causes 502 on ALTCHA Captcha Endpoint

## Problem

Production environment returned **502 Bad Gateway** for `/api/v1/captcha/challenge?endpoint=login` after a backend container rebuild. Login and registration were blocked because the ALTCHA captcha widget could not fetch challenges. All other containers appeared healthy.

## Symptoms

- `GET /api/v1/captcha/challenge?endpoint=login` returned 502 Bad Gateway
- ALTCHA widget in login/registration pages displayed error state
- Backend container logs showed no errors; endpoint registered correctly
- Direct requests to the backend container's new IP (e.g. `172.23.0.7:8000`) succeeded
- `docker ps` showed all containers as healthy

## What Didn't Work

- **Checking container health**: `docker ps` showed all containers healthy — misleading, didn't reveal DNS issue
- **Checking backend logs**: No errors in backend logs — endpoint was registered and working
- **Assuming backend failure**: The backend was fine; the issue was purely at the nginx proxy layer

## Solution

### Immediate Fix

Restart the nginx container to force DNS re-resolution:

```bash
docker restart numina-nginx
```

This reloads the nginx config, re-resolves upstream hostnames, and routes to the new backend IP.

### CSP Headers for ALTCHA

The ALTCHA captcha widget requires additional Content Security Policy headers. Added to `frontend/apps/main/nginx.conf`:

- `script-src`: added `'unsafe-eval'` (ALTCHA PoW computation)
- `worker-src`: added `'self' blob:` (ALTCHA Web Workers)
- `img-src`: added `blob:` (captcha image rendering)

Commit: `14ac605b fix(nginx): add blob: to CSP for ALTCHA Web Workers and images` (local HEAD as of this writing; SHA may be rewritten on push/rebase)

### Key Files

- `frontend/apps/main/nginx.conf` — CSP header configuration and upstream block
- `server/apps/backend/app/routers/captcha.py` — ALTCHA challenge endpoint
- `server/apps/backend/app/auth/captcha.py` — Captcha verification dependency

## Why This Works

Nginx's `upstream backend` block caches DNS resolution at startup. When the backend container was rebuilt (e.g. `docker-compose up -d --build`), Docker assigned it a new IP address. Nginx continued routing to the stale IP because its DNS cache was never refreshed automatically.

Key detail: Docker's embedded DNS (`127.0.0.11`) resolves container names, but nginx resolves upstream hostnames once at config load time and caches the result for the lifetime of the worker process. A container rebuild does not trigger a config reload.

Using `docker restart numina-nginx` forces nginx to reload its configuration and re-resolve the upstream hostname, picking up the new backend IP.

## Prevention

### Option A: Nginx `resolver` Directive (Recommended)

Add a `resolver` directive with a short TTL inside the `location` block that proxies to the backend. This forces nginx to re-resolve DNS at the specified interval instead of caching indefinitely:

```nginx
location /api/ {
    resolver 127.0.0.11 valid=10s;
    set $backend http://backend:8000;
    proxy_pass $backend;
    # ... other proxy_* directives
}
```

Using a variable (`$backend`) forces nginx to use the resolver at runtime rather than at config-load time.

### Option B: Restart After Rebuilds

Document that any `docker-compose up -d --build` for the backend must be followed by `docker restart numina-nginx`. This is fragile and should only be a stopgap.

### Option C: Upstream Health Checks

If using nginx Plus, configure `health_check` for the upstream. For open-source nginx, consider using a sidecar or `docker-compose` healthcheck with `depends_on` condition to trigger nginx reload on backend IP change.

## Lessons Learned

1. **Nginx DNS caching is silent**: There is no error or warning when an upstream IP becomes stale. The first symptom is 502 for all proxied requests.
2. **Container rebuilds change IPs**: Any `docker-compose up -d --build` or `docker-compose up -d` that recreates a container assigns a new IP. Nginx must be restarted or configured with `resolver`.
3. **Diagnosis pattern**: If backend logs are clean but nginx returns 502, test the backend directly by IP. If that works, it is almost always a stale DNS cache.
4. **CSP and third-party widgets**: When adding client-side security features (captcha, PoW challenges), verify CSP headers allow required resources (`blob:` workers, `unsafe-eval`).

## Related Issues

- `docs/solutions/best-practices/altcha-captcha-best-practices-2026-04-03.md` — ALTCHA captcha mechanism (different layer: inner captcha vs. infra proxy)
- `docs/solutions/integration-issues/stream-closure-fix-2026-06-15.md` — another integration issue at the nginx/proxy boundary
- Docker Compose networking documentation on DNS resolution
- Nginx `resolver` directive documentation
