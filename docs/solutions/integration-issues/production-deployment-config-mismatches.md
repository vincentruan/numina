---
title: "Production deployment config mismatches (CSP, connection pool, volume mounts)"
date: 2026-08-13
category: integration-issues
module: infrastructure
problem_type: integration_issue
component: tooling
severity: high
root_cause: config_error
resolution_type: config_change
symptoms:
  - "Outer nginx and inner nginx both set CSP headers; browser intersects them, outer default-src 'self' blocks inner worker-src blob:, breaking Altcha CAPTCHA on /join-family share page"
  - "Supabase session mode limits 15 connections total; pool_size=20 per service exhausts connections with 3 services, causing EMAXCONNSESSION errors and intermittent 500s"
  - "HTTP server block has two location /uploads/ directives, nginx fails to restart with 'duplicate location' error"
  - "3D icon assets not volume-mounted in production docker-compose, icons not displayed in IconPicker"
related_components:
  - database
  - development_workflow
tags:
  - nginx
  - docker-compose
  - deployment
  - production
  - csp-header
  - connection-pool
  - volume-mount
---

# Production deployment config mismatches (CSP, connection pool, volume mounts)

## Problem

After deploying the asset icon picker feature (PR #107) to production, four independent configuration issues were discovered — all sharing a common pattern: configurations that worked in the local dev environment broke in production due to environment-specific differences (layered nginx, Supabase PostgreSQL, GHCR image without LFS assets). Each issue caused a distinct user-visible failure.

## Symptoms

- **Share link page broken**: `/join-family` form submission failed silently. Altcha CAPTCHA's blob worker was blocked because the outer nginx's `Content-Security-Policy: default-src 'self'` header intersected with the inner nginx's `worker-src 'self' blob:` directive (`nginx.production.conf:252-258` location /). The `/finance` route also showed a white screen because the stricter CSP blocked lazy-loaded Vue chunks (session history).
- **Intermittent 500 errors**: Wish list, asset list, and /finance pages returned 500 errors sporadically. Backend logs showed 144 `EMAXCONNSESSION` errors in one hour (session history). Supabase serverless pooler (session mode, port 5432) caps at 15 total connections; each of the 3 services (backend, agent, scheduler-worker) could open up to 40 connections (`pool_size=20` + `max_overflow=20`), yielding a potential 120 connections — far exceeding the limit.
- **nginx restart failure**: `nginx -t` reported "duplicate location" error. The HTTP→HTTPS redirect server block had two `location /uploads/` directives at lines 49 and 64. Discovered during deployment when the nginx container failed to start, resulting in 502 errors for all traffic (session history).
- **Missing 3D icons**: IconPicker showed empty grid in production. 3D icon PNGs (448MB, LFS-tracked) and WebP thumbnails (114MB, gitignored derived files) were not available inside the container. External requests returned 404 even after initial fix — Cloudflare had cached the earlier 404 responses (session history).

## What Didn't Work

- **Committing WebP thumbnails to Git LFS** (session history): Initially attempted to commit 6021 WebP thumbnails (114MB) to git. Rejected because thumbnails are derived files (same principle as build output directories or node_modules), waste GitHub LFS quota (1GB free, already using 448MB for originals), and force 114MB re-push on every icon change. Final approach: generate thumbnails at Docker build time.
- **Git LFS in Docker build context** (session history): CI had `lfs: true` on checkout, but the Docker build context doesn't automatically pull LFS files. Symlinks to LFS-tracked files don't survive `COPY` into the image. The initial assumption that LFS files would be available in Docker build was wrong.
- **Absolute symlinks in container** (session history): After volume-mounting icons to the server, symlinks used absolute host paths which don't exist inside the container. Relative symlinks also failed because they pointed outside the mount boundary. Solution: generate everything at build time instead.
- **Cloudflare caching 404s** (session history): After deploying icons via volume mount, external requests returned 404 even though localhost returned 200. Cloudflare had cached the earlier 404 responses. Cache-busting query params confirmed the icons were actually being served correctly.
- **Direct path to root cause in each case.** These were not complex debugging exercises — the symptoms pointed clearly to configuration mismatches once production logs were examined. The real challenge was that none of these issues were visible during development, where the environment differs in four key ways: (1) single nginx layer (no outer proxy), (2) SQLite database (no connection pool limits), (3) full nginx config without duplication, (4) local filesystem serving (no container image boundary).

## Solution

### Fix 1: Remove duplicate CSP headers (c527687c)

Removed CSP headers from the outer nginx proxy (`nginx.production.conf`). The inner nginx (inside the frontend-main container) sets per-request CSP with nonce injection for scripts — this must be the sole source of CSP.

```nginx
# BEFORE — outer nginx set its own CSP, causing browser intersection
location / {
    proxy_pass http://frontend-main/;
    add_header Content-Security-Policy "default-src 'self'; ..." always;
}

# AFTER — outer nginx only sets non-CSP security headers
# NOTE: CSP is set by the inner nginx with per-request nonce injection.
# Do NOT add CSP here — duplicate CSP headers cause the browser
# to enforce the intersection of both policies.
location / {
    proxy_pass http://frontend-main/;
    # No CSP — inner nginx handles it
}
```

Also removed `add_header Content-Security-Policy "default-src 'self'" always;` from the `location /api/` block.

### Fix 2: Reduce connection pool for Supabase (abc21d7c)

Reduced SQLAlchemy pool sizes in `server/packages/db/engine.py:61-62` from `pool_size=20, max_overflow=20` to `pool_size=3, max_overflow=2`. With 3 services, each now opens at most 5 connections (total ≤15).

```python
# BEFORE — far too large for Supabase serverless pooler
def get_pool_config(self) -> dict:
    return {
        "pool_size": 20,
        "max_overflow": 20,
        ...
    }

# AFTER — conservative for 15-connection Supabase session mode limit
def get_pool_config(self) -> dict:
    # Supabase serverless pooler limits: 15 connections in session mode.
    # With 3 services (backend, agent, scheduler-worker), each gets ~5 connections max.
    return {
        "pool_size": 3,
        "max_overflow": 2,
        "pool_timeout": 10,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
```

Also switched production DATABASE_URL to transaction mode (port 6543) for higher connection limits.

### Fix 3: Remove duplicate nginx location (9cebf24a)

The HTTP server block (ports 80 -> 443 redirect) in `nginx.production.conf` had two `location /uploads/` directives - one at line 49 and a duplicate at line 64. nginx rejects duplicate location directives within the same server block, causing the container to fail on restart. Removed the duplicate at line 64. The remaining `location /uploads/` at line 49 (HTTP block) and line 210 (HTTPS block) are in different server blocks, so they are not duplicates.

### Fix 4: Icon assets availability (ac0c9f54 -> 2f156488)

The initial fix (ac0c9f54) added a volume mount to `docker-compose.production.yml` for the frontend-main service to make LFS-tracked 3D icon PNGs and WebP thumbnails available inside the container at runtime. The same commit also added loading UX (skeleton shimmer, loading spinner, grid-level loading indicator) to the IconPicker.

```yaml
# Phase 1 (ac0c9f54) - volume mount, later removed
frontend-main:
  volumes:
    - ${NUMINA_DATA_DIR:-./.numina/data}/icons:/usr/share/nginx/html/icons:ro
```

**Evolution of the icon fix** (session history): The volume mount was Phase 1. Phase 2 (commit f7601c74) moved thumbnail generation into the Dockerfile (`deploy-icons.ts` creates symlinks, `generate-icon-thumbnails.ts` generates WebP from PNGs during build). Phase 3 (commit 2f156488) removed the volume mount entirely - the image became self-contained. Phase 4 added BuildKit cache mount + Dockerfile layer reordering so thumbnail generation happens before `COPY` of app source, enabling Docker layer cache to skip regeneration when only app code changes (not icons). Conventional code-only commits saw thumbnail generation drop from ~30-60s to 0s. **The current production state has no icon volume mount** - icons are baked into the GHCR image at build time.

## Why This Works

All four issues stem from the same root cause: **dev/prod environment asymmetry**. The local development environment masks these problems because:

1. **Single nginx layer** — dev uses `docker-compose.yml` with one nginx, no outer proxy. The CSP intersection only appears when an outer nginx (production reverse proxy) adds its own headers.
2. **SQLite vs PostgreSQL** — dev uses SQLite (no connection pool, no limits). The pool exhaustion only manifests with Supabase's serverless pooler connection cap.
3. **Local filesystem** — dev serves from the host filesystem; all icon files are available. Production GHCR images don't include LFS-tracked binaries by default, so icon assets must either be volume-mounted or generated at Docker build time (the final approach).
4. **Nginx config divergence** — the production nginx config (`nginx.production.conf`) has evolved separately from the dev config. Duplicate location blocks accumulated over time and were only caught when nginx tried to reload.

The fixes work because they align the production configuration with the actual runtime constraints: single-source CSP, pool sizes matched to provider limits, no duplicate config blocks, and icon assets generated at Docker build time so images are self-contained.

## Prevention

- **nginx config validation before deploy**: Always run `nginx -t` on the production config after changes. CI could validate `nginx.production.conf` syntax with `docker run nginx nginx -t -c /etc/nginx/conf.d/nginx.production.conf`.
- **Connection pool documentation**: Document the Supabase connection limit (15 in session mode) in `server/packages/db/engine.py` alongside pool config. Any change to service count or pool sizes must recalculate `services × (pool_size + max_overflow) ≤ limit`.
- **CSP header ownership rule**: Establish that exactly one nginx layer owns CSP. Add a comment in both nginx configs referencing this rule. The inner nginx owns CSP (nonce-based); outer nginx must not add CSP headers.
- **Production dry-run checklist**: Before each production deploy, verify: (1) `nginx -t` passes, (2) volume mounts in docker-compose match expected data directories, (3) connection pool sizes are within provider limits, (4) no duplicate security headers across proxy layers.
- **Staging environment parity**: Consider a staging deployment that mirrors production's layered nginx + managed PostgreSQL to catch these mismatches before they hit production.

## Related Issues

- Related doc: [nginx stale DNS upstream cache](./nginx-stale-dns-upstream-cache.md) — same nginx config file, same production deployment context, but different root cause (DNS caching vs CSP duplication). Moderate overlap in prevention recommendations.
- Related doc: [Altcha CAPTCHA best practices](../best-practices/altcha-captcha-best-practices-2026-04-03.md) — CSP headers for Altcha were originally added to the same nginx.conf file where today's duplicate CSP was fixed.
- Commits: c527687c (CSP), abc21d7c (pool), 9cebf24a (duplicate location), ac0c9f54 (volume mount)
