---
title: Cache Key Granularity Must Match the Narrowest Data Scope
date: 2026-04-27
category: docs/solutions/best-practices
module: backend
problem_type: best_practice
component: database
severity: high
applies_when:
  - Designing cache keys for any endpoint that aggregates data from multiple scopes (e.g., family + user)
  - Any cached response that includes user-level preferences (currency, locale, timezone, role-based filters)
tags: [cache-key-granularity, cache-invalidation, multi-user, currency, dashboard, data-consistency]
---

# Cache Key Granularity Must Match the Narrowest Data Scope

## Context

The dashboard bundle endpoint cached its response at `dashboard:bundle:{family_id}`. The cached payload included currency-converted totals, and `default_currency` is a per-user preference. When two family members with different currency preferences used the app, they shared the same cache entry — one member saw the other's currency totals. The bug was silent, intermittent, and only reproducible with two simultaneous users.

Three options were considered: fix the key to include `user_id`, remove the cache but keep the bundle endpoint, or remove the bundle endpoint entirely. The third option was chosen — for a self-hosted single-family deployment, DB query volume is small enough that a 60–90s cache TTL provides negligible performance benefit, while the invalidation complexity is disproportionate. (session history)

The random TTL jitter (60–90s) used to avoid cache stampedes was a workaround masking the deeper problem: the invalidation path was incomplete. `PUT /auth/profile` (currency change) and the exchange rate scheduler both mutated dashboard inputs without invalidating the cache.

## Guidance

**Rule**: Cache key granularity must match the finest-grained input that affects the output.

Before caching any aggregated endpoint, enumerate all inputs that affect the response. If any input is user-scoped, the cache key must include the user dimension — or the cache must be removed.

```python
# Wrong — family-level key, but payload contains user-level default_currency
cache_key = f"dashboard:bundle:{family_id}"

# Correct — include every dimension that affects the output
cache_key = f"dashboard:bundle:{family_id}:{user_id}:{default_currency}"

# Often better for small deployments — skip the cache entirely
# and use parallel queries instead
async def get_dashboard(family_id: int, user_id: int):
    assets, prefs = await asyncio.gather(
        asset_service.get_family_summary(family_id),   # family-scoped
        user_service.get_preferences(user_id),          # user-scoped
    )
    return build_dashboard(assets, prefs)
```

**Two-phase parallel loading** as an alternative to bundle caching:

```python
# Phase 1 — blocks loading state, critical path
overview, states = await asyncio.gather(
    dashboard_service.get_overview(family_id, user_id),
    dashboard_service.get_states_summary(family_id),
)
loading = False  # first paint

# Phase 2 — background, non-blocking
asyncio.gather(
    dashboard_service.get_allocation(family_id),
    dashboard_service.get_trend(family_id),
    dashboard_service.get_low_usage(family_id),
    dashboard_service.get_expiring_soon(family_id),
)
```

**Invalidation completeness checklist** — before shipping a cache, list every write path that mutates the cached data:

| Write operation | Invalidates cache? |
|---|---|
| Asset create/update/delete | ✓ |
| Liability create/update/delete | ✓ |
| `PUT /auth/profile` (currency change) | ✗ ← missed |
| Exchange rate scheduler update | ✗ ← missed |

If any row is ✗, either add invalidation or remove the cache.

## Why This Matters

Incorrect cache granularity produces silent data correctness bugs — users see stale or wrong data with no error. In a financial dashboard, showing wrong currency totals erodes trust and can cause real decisions to be made on bad data. The fix is not "add more invalidation" — it's to align cache key scope with data scope from the start.

The random TTL anti-pattern (`random.randint(60, 90)`) is a red flag: it signals that the developer knows invalidation is incomplete and is using TTL expiry as a substitute. If you find yourself randomizing TTL to avoid stampedes, ask whether the cache is worth keeping at all.

## When to Apply

Before caching any aggregated endpoint, ask:
1. Does any user-level input (currency, locale, role, feature flag) affect this output?
2. Is the complete list of write paths that invalidate this data known and handled?
3. Is the performance benefit measurable and worth the complexity?

For self-hosted, small-scale deployments: when in doubt, skip the cache. Parallel DB queries are fast enough.

## Examples

**Wrong** — family-level key, user-level data inside:
```python
cache_key = f"dashboard:bundle:{family_id}"
# User A (USD) and User B (CNY) share the same cached bundle
# User B sees User A's USD totals
```

**Correct** — key includes all dimensions that affect output:
```python
cache_key = f"dashboard:bundle:{family_id}:{user_id}:{default_currency}"
```

**Best for this project** — no bundle cache, parallel sub-queries:
```python
# Each sub-endpoint cached independently at correct granularity
# or not cached at all — DB is fast enough for a family of 2-5
```

## Related

- `docs/solutions/best-practices/security-protection.md` — rate-limit cache uses correct per-username keys (prior art for cache key scoping)
- Dashboard cache removal spec: `docs/superpowers/specs/2026-04-26-remove-dashboard-bundle-cache-design.md`
