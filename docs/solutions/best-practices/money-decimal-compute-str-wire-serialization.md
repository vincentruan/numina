---
title: Money Type Split — Decimal in Compute, str on the Wire (Float→Numeric Migration)
date: 2026-07-20
category: best-practices
module: backend
problem_type: best_practice
component: database
related_components: ["service_object"]
severity: medium
applies_when:
  - "Storing currency amounts in SQLAlchemy models — use Numeric(18,2) (Decimal), never Float, to avoid binary-float rounding drift over arithmetic"
  - "Migrating an existing Float money column to Numeric — coerce Decimal→float only at aggregation boundaries that sum mixed float/Decimal columns"
  - "Defining Pydantic v2 request schemas for money fields — type Decimal with a field_validator(mode='before') that coerces Decimal(str(v)) to tolerate JSON floats/strings without precision loss"
  - "Defining Pydantic v2 response schemas (SnowflakeBase) for money fields — type str with field_validator(mode='before') doing str(Decimal(v).quantize(Decimal('0.01'))) so money crosses the wire as a string"
  - "Doing amortization or other multi-step currency math in a compute layer — keep all arithmetic in Decimal and pre-quantize at construction to satisfy mypy and avoid serialization warnings"
tags: [money-as-str, decimal, numeric, float-to-numeric, pydantic, json-serialization, amortization, sqlalchemy, alembic]
last_refreshed: 2026-07-31
---

# Money Type Split — Decimal in Compute, str on the Wire

## Context

Numina's `CLAUDE.md` has long carried a "money/bigint as strings" wire convention: JavaScript's `Number` is an IEEE-754 double that loses precision beyond 2^53 (~9 quadrillion), so currency amounts and bigint IDs must cross the JSON boundary as strings. The bigint half of this convention was already enforced by `SnowflakeBase` (see [`snowflake-id-json-string-serialization-2026-04-27.md`](./snowflake-id-json-string-serialization-2026-04-27.md)), which auto-converts `int` fields named `id` or ending in `_id` to `str` during serialization. The money half, however, was only half-enforced: response schemas were stringified, but the underlying SQLAlchemy columns were still `Float`, so the value entering Python was already a binary float that had silently lost precision before any serialization happened.

This latent gap was forced into the open by the **Plan B P0 family-finance business touchpoints** on branch `feat/two-ai-apps-unified-dispatch` (now merged to main). Plan B added a cluster of money-touching features — W1 savings (`wish_savings_log` plus endpoints plus ignore-debt-warning), L1/L2 amortization calculator plus `POST /liabilities/simulate`, D2/A1a finance-coach dashboard card with an SSE stream, W4 wish-advice card with cache and LLM wire, W5 debt-warning linkage (`FamilyDebtThresholds` plus `GET/PUT /family/debt-thresholds`), and A1b `/ai/context`. The L1/L2 amortization calculator was the inflection point: it iterates month-by-month up to a 1200-month cap (`server/packages/domain/liability_calculator.py`), multiplying `balance * monthly_rate` and quantizing each iteration. Running that loop on a `float` principal would compound rounding drift across a hundred years of iterations — exactly the failure mode `Decimal` exists to prevent. Implementing the calculator in `Decimal` immediately surfaced the mismatch: the model fed it `Float` columns, so either the calculator down-graded to float (defeating the purpose) or the model had to migrate. The latter was correct, and the migration (now merged to main, Alembic revision `b2c3d4e5f6a7`) cascaded into the schema layer (request and response validators) and five aggregation-boundary sites that sum liabilities against float asset values.

## Guidance

The pattern is a four-layer split, with one explicit carve-out for percentages. The rule of thumb: **currency amounts → `Numeric(18,2)` / `Decimal` in Python / `str` on the wire; rates and percentages → `Float`**. Currency needs exact decimal representation (cents must be exact) and string serialization (JS precision loss); a rate like `4.25%` is a small number read at 2-4 decimal places where binary-float precision is more than adequate, and keeping it `Float` avoids forcing every rate-reading site into a `Decimal` coercion.

**Layer 1 — Model.** Money columns are `Mapped[Decimal] = mapped_column(Numeric(18, 2), ...)`. From `server/apps/backend/app/models/liability.py:33-36`:

```python
# Money fields are NUMERIC(18,2) — Decimal in Python, serialized as str on
# the wire (SnowflakeBase money-as-str convention, CLAUDE.md §bigint). Was
# Float pre-T8b (precision risk for currency); migrated to Numeric.
original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
```

Note `interest_rate` stays `Float` — it is a percentage, not a currency amount.

**Layer 2 — Request/input schema.** Money fields are typed `Decimal`, and a `mode="before"` validator tolerates JSON float-or-string input without precision loss by routing through `Decimal(str(v))`. From `server/apps/backend/app/schemas/liability.py` (same shape on `LiabilityUpdate` and `PaymentRequest`):

```python
@field_validator("original_amount", "remaining_amount", "monthly_payment", mode="before")
@classmethod
def _coerce_money(cls, v):
    if v is None or isinstance(v, Decimal):
        return v
    return Decimal(str(v))
```

The `str(v)` intermediate is load-bearing: `Decimal(0.1)` constructs from the binary-float approximation (`0.1000000000000000055...`), whereas `Decimal(str(0.1))` constructs from `"0.1"`. Always round-trip through `str` at the input boundary.

**Layer 3 — Response schema.** Money fields are typed `str`, and a `mode="before"` validator quantizes to 2 decimals and stringifies. From `LiabilityResponse(SnowflakeBase)` in `server/apps/backend/app/schemas/liability.py`:

```python
@field_validator("original_amount", "remaining_amount", "monthly_payment", mode="before")
@classmethod
def _coerce_money(cls, v):
    if v is None or isinstance(v, str):
        return v
    return str(Decimal(v).quantize(Decimal("0.01")))
```

This is the half of the convention that prevents JS precision loss: the field is typed `str`, so Pydantic v2 emits a JSON string, and the explicit `quantize(Decimal("0.01"))` guarantees exactly two decimal places regardless of how the value arrived.

**Layer 4 — Compute layer.** All arithmetic stays in `Decimal`. Pre-quantize constants at construction (module-level `TWO_PLACES = Decimal("0.01")`) to satisfy mypy and avoid serialization warnings. From `server/packages/domain/liability_calculator.py`:

```python
from decimal import ROUND_HALF_UP, Decimal

MAX_MONTHS = 1200  # 100-year cap — backstop against non-converging inputs.
TWO_PLACES = Decimal("0.01")
BALANCE_TOLERANCE = Decimal("0.005")

def _q(v: Decimal) -> Decimal:
    """Quantize to 2 decimals (cents)."""
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
# ...inside the amortization loop:
monthly_rate = annual_rate / Decimal("100") / Decimal("12")
interest = _q(balance * monthly_rate)
balance = _q(balance - principal)
total_interest = _q(total_interest + interest)
```

**Layer 5 — Aggregation boundaries.** When a `Decimal` liability amount must be summed with `Float` asset values (assets still use `Float` for `current_value`), coerce the `Decimal` to `float` at the boundary, with a comment explaining why. The aggregate is a dashboard stat where float precision is sufficient, and mixing `Decimal + float` raises `TypeError`. From `server/apps/backend/app/routers/family.py:127-130`:

```python
# Coerce to float: asset values are Float, liability amounts are now
# Decimal (Numeric); mixing them raises TypeError. The aggregate is a
# dashboard stat where float precision is sufficient.
total_assets = float(total_assets or 0)
total_liabilities = float(total_liabilities or 0)
```

The same boundary coercion appears at four service-layer sites: `server/apps/backend/app/services/dashboard.py:82` (`float(l.remaining_amount)` before `ExchangeRateService.convert`), `server/apps/backend/app/services/snapshot.py:59` (`float(l.remaining_amount or 0)`), `server/apps/backend/app/services/projection.py:44-45` (`float(li.get("remaining_amount", 0) or 0)` and the matching `monthly_payment`), and `server/apps/backend/app/services/whatif.py:16` (`float(li.get("monthly_payment") or 0) * 12`). Each carries a comment noting that the value may be `Decimal` (from the model) or `str` (from the API) and is coerced so the arithmetic below stays in one numeric type.

**The currency-vs-rate rule, restated.** When adding a new numeric field to a money model, ask: is this an amount of money (a balance, a payment, a fee)? Then `Numeric(18,2)` / `Decimal` / `str`. Is this a rate or percentage (an interest rate, a tax rate, an inflation rate)? Then `Float`. Mixing the two — making a rate `Decimal` or a currency amount `Float` — either over-engineers every rate reader or re-introduces the precision hazard the split exists to close.

## Why This Matters

Three distinct precision problems converge on currency, and the money-type split addresses a different one at each layer.

**Binary float cannot represent decimal currency.** Python `float` and JS `Number` are both IEEE-754 doubles — `0.1 + 0.2` yields `0.30000000000000004`, not `0.3`. A mortgage balance stored as `Float` is already an approximation the moment it is written. `Decimal` is a base-10 type: `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` exactly. For a field denominated in cents, this is not a pedantic distinction — it is the difference between a balance that reconciles and one that drifts.

**Drift compounds over long amortization.** The L1/L2 calculator iterates month-by-month, multiplying `balance * monthly_rate` and subtracting principal, up to a 1200-month (100-year) cap (`liability_calculator.py`). A sub-cent error per iteration, repeated 1200 times against a shrinking balance, does not stay sub-cent — it accumulates into visible drift between the baseline and "extra monthly payment" scenarios, which is precisely the 省息 (interest saved) figure the L2 forecast displays to the user. Running the loop in `Decimal` with explicit `_q(...)` quantization at each step keeps every iteration exact.

**JSON has no `Decimal` type.** This is the gap that makes "Decimal in compute" alone insufficient. Pydantic v2 serializes a `Decimal` field as a JSON number by default, which means it round-trips through a float at the JSON layer — reintroducing the precision loss the `Decimal` was meant to prevent. The only way to force a string onto the wire is to type the response field `str` (and, to guarantee 2-decimal formatting, quantize in a `mode="before"` validator). The response schema in `liability.py` does exactly this. Without that final `str` typing, a model full of `Numeric(18,2)` columns would still emit lossy floats to the frontend.

**The currency-vs-rate distinction avoids over-engineering.** If `interest_rate` were also `Decimal`, every site that reads a rate — the amortization calculator (`annual_rate / Decimal("100") / Decimal("12")`), the debt-warning composable, the dashboard — would need its own `Decimal` coercion, and the boundary sites that currently do a clean `float()` coercion would need reworking. A percentage read at 2-4 decimal places does not benefit from `Decimal`'s exactness; the cost-benefit favors `Float`.

## When to Apply

- Any money/currency field on a SQLAlchemy model exposed via a JSON API, especially when the field participates in arithmetic (amortization, projection, aggregation across assets and liabilities).
- Migrating a `Float` money column to `Numeric`. The migration is mechanical but touches all four layers: the model column type, the request-schema validator (add `mode="before"` `Decimal(str(v))`), the response-schema validator (add `mode="before"` `str(Decimal(v).quantize(Decimal("0.01")))` and retype the field `str`), and every aggregation-boundary site that sums the now-`Decimal` value against `Float` values (add `float(...)` with an explanatory comment). The migration revision `b2c3d4e5f6a7` (`server/apps/backend/alembic/versions/b2c3d4e5f6a7_liability_float_to_numeric.py`) is a reference for the Alembic shape — on SQLite it requires `batch_alter_table` because SQLite cannot `ALTER COLUMN` type directly.
- Adding a new money column — declare it `Numeric(18, 2)` from the start, with the request and response validators in place on day one, to avoid inheriting the original debt.
- Building a compute layer (amortization, forecasting) where binary-float drift would compound over many iterations.

Do **not** apply the `Decimal` half to rates or percentages — leave those `Float`. Do **not** apply it to fields that are pure counts or quantities (number of months, number of members) — those are `int`. And do **not** coerce to `float` at a boundary unless the downstream consumer genuinely expects `float` and the value is a stat where approximation is acceptable; a value that will be displayed to the user as an exact balance should stay `str` end-to-end.

## Examples

**The Float→Numeric migration (before/after).** Before the migration, the liability model declared currency as:

```python
original_amount: Mapped[float] = mapped_column(Float, nullable=False)
remaining_amount: Mapped[float] = mapped_column(Float, nullable=False)
monthly_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
```

A `float` principal fed directly into the amortization calculator would drift over 1200 iterations, and a `float` response field would serialize as a JSON number (lossy at the JS layer). After the migration (now merged to main), the columns are `Numeric(18, 2)` and `Mapped[Decimal]` (shown in the Guidance Layer 1 snippet above). The Alembic revision `b2c3d4e5f6a7` performs the type change for all three currency columns while leaving `interest_rate` on `Float`:

```python
with op.batch_alter_table('liabilities', schema=None) as batch_op:
    batch_op.alter_column(
        'original_amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    # ... remaining_amount and monthly_payment follow the same shape ...
```

The `batch_alter_table` wrapper is required because SQLite (the default dev/test DB) does not support direct column type changes; Alembic performs the table-recreate dance transparently. Existing `Float` values coerce cleanly to `NUMERIC(18,2)`. *(auto memory [claude] — liability-float-to-numeric-migration)*

**The aggregation-boundary coercion.** The family aggregate endpoint sums asset values (`Float`) against liability balances (now `Decimal`). Doing `total_assets - total_liabilities` directly raises `TypeError`. The fix coerces both sides to `float` at the boundary (`server/apps/backend/app/routers/family.py:127-130`):

```python
# Coerce to float: asset values are Float, liability amounts are now
# Decimal (Numeric); mixing them raises TypeError. The aggregate is a
# dashboard stat where float precision is sufficient.
total_assets = float(total_assets or 0)
total_liabilities = float(total_liabilities or 0)
```

The same pattern repeats at `dashboard.py:82`, `snapshot.py:59`, `projection.py:44-45`, and `whatif.py:16`. The key discipline: coerce **at the boundary**, not earlier — keep the value `Decimal` for as long as possible so that any further computation remains exact, and drop to `float` only at the moment of mixing.

**The rate-stays-Float decision.** `interest_rate` (`liability.py:36`) is `Mapped[float | None] = mapped_column(Float, nullable=True)`. It feeds the amortization calculator as `annual_rate`, where it is divided by `Decimal("100") / Decimal("12")` to produce a monthly rate. The calculator accepts `annual_rate: Decimal | None`, so the single coercion happens at the calculator's entry — the call site converts the model's `float` rate to `Decimal` once, and every subsequent operation stays in `Decimal`. This is the pragmatic shape of the currency-vs-rate rule: the rate lives as `Float` on the model and in the API (no per-reader coercion), and crosses into `Decimal` exactly once, at the compute boundary, where the arithmetic that needs exactness begins. If the rate were `Decimal` on the model, the coercion would still exist — it would just be scattered across every reader instead of centralized at the one compute entry point. *(auto memory [claude] — t9-afford-bar-savings-strategy-ui: expected_price kept as number to avoid str cascade)*

## Related

- **Cross-reference** [`snowflake-id-json-string-serialization-2026-04-27.md`](./snowflake-id-json-string-serialization-2026-04-27.md) — the ID/serialization half of the same str-on-the-wire convention. Both rely on `SnowflakeBase` at the JSON boundary and share the JS-double-precision root cause. This doc is the money half: same prevention philosophy (keep Python native type, serialize to `str` at boundary), different domain (currency columns vs Snowflake IDs).
- **Related** [`fastapi-pydantic-validation-error-localization-2026-04-16.md`](./fastapi-pydantic-validation-error-localization-2026-04-16.md) — shares the Pydantic v2 / FastAPI schema layer this doc's `field_validator` + Decimal-input/str-output schemas sit on, but solves a different problem (422 validation error localization).
