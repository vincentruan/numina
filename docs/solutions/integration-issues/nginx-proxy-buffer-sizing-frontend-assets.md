---
title: "Nginx proxy buffer too small for large JS bundles and CJK fonts — buffered to temp file"
date: "2026-08-20"
category: integration-issues
module: infrastructure
problem_type: integration_issue
component: tooling
severity: medium
symptoms:
  - "Nginx error log shows 'upstream sent too big response while reading response header from upstream' or 'buffered to a temporary file' warnings"
  - "Large JS bundles (2+ MB) and Chinese font files (5+ MB) served slowly through nginx proxy"
  - "Frontend static assets intermittently fail to load through the reverse proxy"
root_cause: config_error
resolution_type: config_change
tags:
  - nginx
  - proxy-buffer
  - static-assets
  - performance
  - chinese-fonts
  - docker
---

# Nginx Proxy Buffer Too Small for Large JS Bundles and CJK Fonts

## Problem

Nginx's default proxy buffer settings (`proxy_buffer_size` 4k or 8k, `proxy_buffers` 4 8k) are too small for modern frontend applications with large JavaScript bundles and CJK (Chinese/Japanese/Korean) font files. When the upstream response exceeds the buffer, nginx writes to a temporary file on disk, causing slow responses and warning messages in the error log.

## Symptoms

- Nginx error log: `[warn] ... an upstream response is buffered to a temporary file /var/cache/nginx/proxy_temp/... while reading upstream`
- Large JS chunk files (Vue/React production bundles, often 1-3 MB gzipped) take noticeably longer to load through nginx than directly.
- Chinese font files (e.g., Noto Sans SC at 5+ MB for full CJK coverage) consistently trigger the temp file buffering.

## Solution

Increase proxy buffer sizes on the frontend `location` blocks in both dev and production nginx configs:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    # ... other proxy settings ...
    proxy_buffer_size 32k;
    proxy_buffers 8 32k;
    proxy_busy_buffers_size 64k;
}

# Frontend static files — same buffer settings
location / {
    proxy_pass http://frontend-main:8080;
    proxy_buffer_size 32k;
    proxy_buffers 8 32k;
    proxy_busy_buffers_size 64k;
}
```

Key settings:
- `proxy_buffer_size 32k` — buffer for the first part of the response (headers)
- `proxy_buffers 8 32k` — 8 buffers of 32k each = 256k total for the response body
- `proxy_busy_buffers_size 64k` — max data nginx can send to the client while still reading the rest from upstream

## Why This Works

The default `proxy_buffer_size` (4k/8k) is designed for small API responses. Modern frontend bundles are much larger:
- Vue/React production JS bundles: 1-3 MB
- CJK web fonts: 5-15 MB (full character set)
- Source maps (if served): even larger

With 256k of buffer space (8 x 32k), most responses fit entirely in memory. Only very large files (15 MB+ fonts) still hit the temp file path, which is acceptable for rare downloads.

## Prevention

- **Rule:** When nginx reverse-proxies frontend apps with large static assets, always increase `proxy_buffers` beyond the default.
- **Baseline:** `proxy_buffers 8 32k` is a good starting point for modern SPAs with CJK fonts.
- **Monitoring:** Check nginx error logs for "buffered to a temporary file" warnings after deploy — they indicate the buffers need further tuning.

## Related Issues

- Related: `docs/solutions/integration-issues/production-deployment-config-mismatches.md` (other nginx/proxy configuration issues)
