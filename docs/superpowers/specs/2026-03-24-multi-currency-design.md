# Multi-Currency Support Design

**Date:** 2026-03-24
**Status:** Approved
**Scope:** Asset/Liability/Wish recording in any currency, unified display in user's default currency via exchange rate conversion

---

## Core Goal

Record amounts in their original currency → display unified in user's default currency → accurate aggregation across all assets.

The fundamental problem: users purchase assets in multiple currencies (USD stocks, HKD property, etc.), but net worth calculations require a single currency baseline. Solution: store original currency + amount, convert at display/aggregation time using cached exchange rates.

---

## Database Schema

### New: `exchange_rates` table

```python
class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    base_currency: Mapped[str] = mapped_column(String(10), default="CNY")  # Always "CNY"
    target_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # target units per 1 CNY
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint('target_currency', 'fetched_at'),)
```

### New: `currencies` table (system-level, not per-user)

```python
class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # "CNY", "USD"
    name_zh: Mapped[str] = mapped_column(String(50), nullable=False)  # "人民币"
    name_en: Mapped[str] = mapped_column(String(50), nullable=False)  # "Chinese Yuan"
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)   # "¥"
    flag_emoji: Mapped[str] = mapped_column(String(10), nullable=False)  # "🇨🇳"
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=999)
```

Favorites are **system-level** (not per-user). All users see the same 13 favorites at the top.

The `currencies` table is seeded on startup with the 13 favorites. All other currencies are populated from the exchange rate API response on first fetch (code + symbol derived from ISO 4217 lookup table in seed data).

### Modified: `wishes` table

Add `currency: Mapped[str] = mapped_column(String(10), default="CNY")`.

### Modified: `liabilities` table

Add `currency: Mapped[str] = mapped_column(String(10), default="CNY")`.

**Note:** `assets` already has `currency` field. `liabilities` does NOT currently have one — this is a new addition.

Schema changes use `Base.metadata.create_all()` (dev) — no Alembic migration needed for development. For production upgrades, add `ALTER TABLE liabilities ADD COLUMN currency VARCHAR(10) DEFAULT 'CNY'` and same for `wishes`.

---

## Favorite Currencies (seeded on startup)

| sort_order | code | name_zh | name_en | symbol | flag |
|---|---|---|---|---|---|
| 1 | CNY | 人民币 | Chinese Yuan | ¥ | 🇨🇳 |
| 2 | USD | 美元 | US Dollar | $ | 🇺🇸 |
| 3 | EUR | 欧元 | Euro | € | 🇪🇺 |
| 4 | JPY | 日元 | Japanese Yen | ¥ | 🇯🇵 |
| 5 | GBP | 英镑 | British Pound | £ | 🇬🇧 |
| 6 | AUD | 澳元 | Australian Dollar | A$ | 🇦🇺 |
| 7 | CAD | 加元 | Canadian Dollar | C$ | 🇨🇦 |
| 8 | CHF | 瑞士法郎 | Swiss Franc | Fr | 🇨🇭 |
| 9 | HKD | 港币 | Hong Kong Dollar | HK$ | 🇭🇰 |
| 10 | SGD | 新加坡元 | Singapore Dollar | S$ | 🇸🇬 |
| 11 | RUB | 卢布 | Russian Ruble | ₽ | 🇷🇺 |
| 12 | INR | 卢比 | Indian Rupee | ₹ | 🇮🇳 |
| 13 | BRL | 巴西雷亚尔 | Brazilian Real | R$ | 🇧🇷 |

---

## Backend Architecture

### ExchangeRateService (`backend/app/services/exchange_rate.py`)

**Synchronous** — matches the existing codebase pattern (all routers/services use `def`, not `async def`).

```python
class ExchangeRateService:
    _cache: dict[str, tuple[float, datetime]] = {}  # { "USD": (0.1374, fetched_at) }

    @classmethod
    def get_rate(cls, target_currency: str, db: Session) -> tuple[float, datetime]:
        # 1. In-memory cache hit → return immediately
        # 2. Cache miss → query DB for latest rate → populate cache → return
        # 3. No DB data → return (1.0, now()) as fallback — caller should not show ⓘ icon

    @classmethod
    def fetch_and_store_rates(cls, db: Session) -> None:
        # httpx.get("https://api.exchangerate-api.com/v4/latest/CNY", timeout=10)
        # Bulk insert all rates with current fetched_at timestamp
        # Also upsert any new currency codes into currencies table (code + symbol only)
        # Clear _cache entirely to force repopulation from fresh DB data

    @classmethod
    def convert(cls, amount: float, from_currency: str, to_currency: str, db: Session) -> float:
        # from == to → return amount unchanged (no DB hit)
        # Convert via CNY as intermediate:
        #   amount_in_cny = amount / rate(from)   [rate = target per 1 CNY]
        #   result = amount_in_cny * rate(to)
        # If rate unavailable → return amount unchanged (1:1 fallback, caller logs warning)
```

**Conversion math** (API returns "X target units per 1 CNY"):
- CNY → USD: `amount * rate["USD"]`
- USD → CNY: `amount / rate["USD"]`
- USD → EUR: `(amount / rate["USD"]) * rate["EUR"]`

**Note on JPY:** JPY has no fractional units. Round converted JPY amounts to nearest integer.

### Scheduler (`backend/app/scheduler.py`)

Uses `BackgroundScheduler` (synchronous) — not `AsyncIOScheduler`.

```python
from apscheduler.schedulers.background import BackgroundScheduler
import random

scheduler = BackgroundScheduler()

def setup_exchange_rate_schedule():
    """Schedule rate updates 08:00–23:00, every 2 hours, with 0–15 min random offset."""
    for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
        offset = random.randint(0, 15)
        scheduler.add_job(
            fetch_rates_job,          # calls ExchangeRateService.fetch_and_store_rates()
            trigger='cron',
            hour=hour,
            minute=offset,
            id=f'exchange_rate_{hour}',
            replace_existing=True,
        )
```

- `scheduler.start()` / `scheduler.shutdown()` called in `main.py` lifespan context
- On fetch failure: log error, keep existing DB rates, retry at next scheduled slot
- On fresh install (no rates in DB): call `fetch_and_store_rates()` immediately during app startup before scheduler starts

**New dependency:** `apscheduler` — add via `uv add apscheduler`. `httpx` is already present.

### New Router (`backend/app/routers/currencies.py`)

```
GET /api/v1/currencies              → list all currencies (favorites first, then alpha by code)
GET /api/v1/currencies/rates        → latest rates for all currencies { rates: {USD: {rate, fetched_at}} }
GET /api/v1/currencies/rates/{code} → latest rate for one currency { rate, fetched_at }
```

All endpoints require authentication (`get_current_user` dependency).

### Dashboard Schema Changes

The following Pydantic schemas in `backend/app/schemas/dashboard.py` need `currency` fields added so the frontend can show the `ⓘ` popover:

| Schema | New fields |
|---|---|
| `TopAssetItem` | `currency: str`, `original_value: float` |
| `DailyCostItem` | `currency: str`, `original_value: float` |
| `LowUsageItem` | `currency: str`, `original_value: float` |
| `InvestmentReturnItem` | `currency: str`, `original_purchase_price: float`, `original_current_value: float` |
| `AllocationItem` | no change — allocation amounts are already aggregated in default currency |
| `OverviewResponse` | no change — totals are aggregated in default currency |

All monetary values in responses are in the user's `default_currency`. `original_value` is the raw stored amount in `currency`.

### Dashboard Aggregation Changes

Conversion logic lives in **service layer** (`backend/app/services/dashboard.py`), consistent with existing patterns. Routers call services; services call `ExchangeRateService.convert()`.

Affected service functions:
- `get_overview()` — convert each asset's `current_value` and liability's `remaining_amount` to `default_currency` before summing
- `get_allocation()` — convert each asset's `current_value` before grouping by category
- `get_top_assets()` — convert `current_value`, keep `original_value` + `currency` in response
- `get_daily_cost()` — convert `daily_cost` and `total_cost`
- `get_low_usage()` — convert `current_value`
- `get_investment_returns()` — convert `purchase_price`, `current_value`, `profit`

### Snapshot Currency Strategy

Snapshots are generated at startup with no user context. Strategy: **always snapshot in CNY** (the system base currency), converting all values at snapshot generation time.

Changes to `backend/app/services/snapshot.py`:
- `generate_snapshots()` calls `ExchangeRateService.convert(value, asset.currency, "CNY", db)` for each asset and liability before summing
- `AssetSnapshot` stores values in CNY
- When the trend chart reads snapshots, it converts the CNY totals to the requesting user's `default_currency` at read time (in `get_trend()` service function)

This means trend chart values are accurate regardless of which family member views them, and historical snapshots remain consistent even if a user changes their `default_currency`.

---

## Frontend Architecture

### New: `useExchangeRate` composable (`frontend/src/composables/useExchangeRate.ts`)

```typescript
// Module-level cache — persists across component instances within a page session
const rateCache = new Map<string, { rate: number; fetched_at: string }>()

export function useExchangeRate() {
  async function getRate(currency: string): Promise<{ rate: number; fetched_at: string } | null>
  // Returns null if fetch fails — caller should not show ⓘ icon

  function getRateInfo(
    originalAmount: number,
    sourceCurrency: string,
    targetCurrency: string,
    rateData: { rate: number; fetched_at: string }
  ): {
    originalText: string   // "$1,000.00"
    rateText: string       // "1 USD = 7.13 CNY"
    updatedAt: string      // "2026-03-24 08:03:00" (zh-CN) or "Mar 24, 2026 08:03:00" (en-US)
  }
}
```

Frontend does **not** perform currency conversion — converted values come from the backend. The composable is used only to fetch rate metadata for the `ⓘ` popover display.

### New: `CurrencyPicker` component (`frontend/src/components/common/CurrencyPicker.vue`)

Shared between Settings page and `CurrencySelector`.

- Search bar: filters by `name_zh`, `name_en`, and `code` simultaneously (case-insensitive)
- Section header "常用货币" / "Popular Currencies": 13 favorites, always visible (not filtered out by search)
- Section header "全部货币" / "All Currencies": remaining currencies, alphabetical by code, filtered by search
- Each row: `🇨🇳 人民币（CNY）¥` (zh-CN) / `🇨🇳 Chinese Yuan (CNY) ¥` (en-US)
- Currently selected currency highlighted with checkmark
- Emits `currency-select` event with currency `code`

### New: `CurrencySelector` component (`frontend/src/components/common/CurrencySelector.vue`)

Used in all amount input forms (AssetForm, LiabilityForm, WishForm).

```
┌─────────────────────────────────────┐
│  [🇨🇳 ¥]  │  10000.00              │
│  ↑ button  │  ↑ numeric input       │
└─────────────────────────────────────┘
```

- Clicking the flag+symbol button opens `CurrencyPicker` as bottom sheet
- Props: `modelValue: { amount: number; currency: string }`
- Emits `update:modelValue` — v-model compatible
- Default currency from user's `default_currency` setting

### Updated: `MoneyDisplay` component

New props:
- `sourceCurrency?: string` — the currency the amount was originally recorded in
- `originalValue?: number` — the original amount before conversion

When `sourceCurrency` is provided AND differs from user's `default_currency`:
- Display the already-converted `amount` (passed from parent, converted by backend)
- Show `ⓘ` icon after the amount
- On click: fetch rate via `useExchangeRate().getRate(sourceCurrency)`, show `van-popover`:
  ```
  $1,000.00（1 USD = 7.13 CNY，汇率更新时间：2026-03-24 08:03:00）
  ```

Expand `CURRENCY_SYMBOLS` map to cover all 13 favorites (currently only has 6). Derive symbols from the `/currencies` API response on app init, stored in a Pinia store.

### New: `useCurrencyStore` Pinia store (`frontend/src/stores/currency.ts`)

```typescript
// Loaded once on app init
interface CurrencyStore {
  currencies: Currency[]          // full list from GET /currencies
  symbolMap: Record<string, string>  // { CNY: '¥', USD: '$', ... }
  flagMap: Record<string, string>    // { CNY: '🇨🇳', USD: '🇺🇸', ... }
  fetchCurrencies(): Promise<void>
}
```

`MoneyDisplay` and `CurrencyPicker` read from this store instead of hardcoded maps.

### Updated: `SettingsPage`

Replace `van-picker` currency selector with `CurrencyPicker` component (full-screen bottom sheet with search).

Settings cell displays: `人民币 (CNY)` / `Chinese Yuan (CNY)` based on current language.

### Updated Pages

| Page | Change |
|---|---|
| `AssetFormPage` | Amount input → `CurrencySelector` |
| `LiabilityFormPage` | Amount inputs (original_amount, monthly_payment) → `CurrencySelector` |
| `WishDetailPage` / `WishListPage` | Amount input → `CurrencySelector`; display → `MoneyDisplay` with `sourceCurrency` + `originalValue` |
| `DashboardPage` | `MoneyDisplay` receives `sourceCurrency` + `originalValue` from API response |

---

## Data Flow

### Write path
```
User enters $1,000 USD in AssetForm
→ POST /assets { purchase_price: 1000, currency: "USD", ... }
→ Stored as-is in DB — no conversion at write time
```

### Read/display path
```
GET /dashboard/top-assets (user default_currency = CNY)
→ Backend service: asset { current_value: 1000, currency: "USD" }
  → ExchangeRateService.convert(1000, "USD", "CNY") = 7,130
  → Response: { current_value: 7130, currency: "USD", original_value: 1000, ... }
→ Frontend: MoneyDisplay amount=7130 sourceCurrency="USD" originalValue=1000
  → Shows: ¥7,130.00 ⓘ
  → Popover: $1,000.00（1 USD = 7.13 CNY，汇率更新时间：2026-03-24 08:03:00）
```

### Snapshot path
```
generate_snapshots() called at startup
→ For each asset: ExchangeRateService.convert(current_value, asset.currency, "CNY")
→ Snapshot stored in CNY
→ GET /dashboard/trend (user default_currency = USD)
  → get_trend() reads CNY snapshots
  → Converts each point: convert(net_worth, "CNY", "USD")
  → Returns trend points in USD
```

### Cache invalidation
```
Scheduler fires → fetch_and_store_rates()
  → Bulk insert new ExchangeRate rows to DB
  → ExchangeRateService._cache.clear()
  → Next request repopulates cache from fresh DB rows
```

---

## i18n Keys

Added to `zh-CN` locale file:
```typescript
currency: {
  searchPlaceholder: '搜索币种名称或代码',
  favorites: '常用货币',
  all: '全部货币',
  selectCurrency: '选择币种',
  rateInfo: '1 {from} = {rate} {to}',
  rateUpdatedAt: '汇率更新时间：{time}',
  fetchFailed: '汇率获取失败，使用缓存数据',
}
```

Added to `en-US` locale file:
```typescript
currency: {
  searchPlaceholder: 'Search by name or code',
  favorites: 'Popular Currencies',
  all: 'All Currencies',
  selectCurrency: 'Select Currency',
  rateInfo: '1 {from} = {rate} {to}',
  rateUpdatedAt: 'Rate updated: {time}',
  fetchFailed: 'Rate fetch failed, using cached data',
}
```

Rate time formatting (via dayjs, already bundled with Vant):
- `zh-CN`: `YYYY-MM-DD HH:mm:ss`
- `en-US`: `MMM DD, YYYY HH:mm:ss`

---

## Error Handling

| Scenario | Behavior |
|---|---|
| API fetch fails | Log error, keep existing DB rates, retry at next scheduled slot |
| No rates in DB (fresh install) | Trigger immediate `fetch_and_store_rates()` on app startup |
| Rate unavailable for specific currency | Return amount unchanged (1:1), do NOT show `ⓘ` icon — avoids showing wildly wrong converted values |
| Frontend rate fetch fails | Do not show `ⓘ` icon, log warning to console |
| JPY conversion | Round to nearest integer (no fractional yen) |

---

## Implementation Order

1. Backend models: `ExchangeRate`, `Currency`, add `currency` to `Liability` + `Wish`
2. Seed: 13 favorite currencies in `seed/currencies.py`
3. `ExchangeRateService` (sync) + startup fetch
4. `BackgroundScheduler` setup in `main.py` lifespan
5. `currencies` router
6. Dashboard service layer: add conversion calls + update response schemas
7. Snapshot service: add conversion calls
8. Frontend: `useCurrencyStore` + fetch on app init
9. Frontend: `CurrencyPicker` component
10. Frontend: `CurrencySelector` component
11. Frontend: `MoneyDisplay` updates (sourceCurrency prop + ⓘ popover)
12. Frontend: `useExchangeRate` composable
13. Frontend: update `SettingsPage`, `AssetFormPage`, `LiabilityFormPage`, `WishDetailPage`
14. i18n keys in both locale files

---

## Dependencies

- **Backend (new):** `apscheduler` — add via `uv add apscheduler`
- **Backend (existing):** `httpx` already present
- **Frontend:** No new dependencies (dayjs already bundled with Vant)
