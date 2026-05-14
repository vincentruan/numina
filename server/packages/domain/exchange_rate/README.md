# packages/domain/exchange_rate

Owns exchange rate fetching from an external API, persistence to the database, and CNY-based currency conversion.

## Public API

| Name | Signature | What it does |
|------|-----------|--------------|
| `ExchangeRateService.get_rate` | `(target_currency: str, db: Session) -> tuple[float, datetime]` | Returns `(rate, fetched_at)` for the target currency relative to CNY. Falls back to `1.0` with a warning if no DB row exists. |
| `ExchangeRateService.fetch_and_store_rates` | `(db: Session) -> bool` | Fetches latest rates from exchangerate-api.com, persists to DB, and clears the in-memory cache. Returns `True` on success. |
| `ExchangeRateService.convert` | `(amount: float, from_currency: str, to_currency: str, db: Session) -> float` | Converts an amount between two currencies using CNY as the intermediate. |

All methods are classmethods on `ExchangeRateService`.

## Consumers

- `apps/backend` — calls `get_rate` and `convert` during asset valuation
- `apps/scheduler_worker` — calls `fetch_and_store_rates` on a scheduled job to refresh rates

## Calling Conventions

`ExchangeRateService` maintains a class-level in-memory cache keyed by currency code with a 4-hour TTL.

- `get_rate` reads from cache first; falls back to DB if the cache entry is missing or stale. If no DB row exists, returns `(1.0, now)` and logs a warning — it does **not** raise.
- `fetch_and_store_rates` clears the entire cache on success. Call this before `get_rate` if you need guaranteed fresh rates.
- All methods take a `Session` parameter. The caller creates and manages the session lifecycle.

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
