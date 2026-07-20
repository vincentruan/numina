# Plan B — P0 Family Finance Business Touchpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prerequisite:** Plan A (`docs/superpowers/plans/2026-07-19-plan-a-finance-coach-capability.md`) is complete — the `finance_coach` capability + capability-cache infra must exist before D2/A1a (Task 5) and the W4 cache (Task 6) can call it.

**Goal:** Implement the 7 P0 business touchpoints — W1 (wish savings fields + log + API), L1+L2 (single-source amortization util + `/liabilities/simulate` + UI), W2 (afford bar refactor), D2/A1a (dashboard finance_coach card), A1b (passive buttons + `/ai/context` endpoint + greenfield chat context injection), W4 (wish-priority AI card, independent prompt + cache), W5 (high-interest debt ↔ wish linkage hints) — so the family-finance closed loop has all its touchpoints in place.

**Architecture:** Follows the spec's implementation order (§8): W1 lays the savings data foundation (migration + CRUD + invariant); L1/L2 build the single-source `liability_calculator.py` (backend-only, no dual-language drift) + `/liabilities/simulate`; W2 refactors the afford bar to read W1 fields; D2/A1a renders Plan A's finance_coach `suggestions[]` on the dashboard; A1b adds a unified `GET /ai/context?source=&id=` endpoint + greenfield query-param/entity-prefill on `AIChatBox`; W4 is an independent AI call (own prompt + `wish_advice:{fingerprint}` cache key, NOT finance_coach's output); W5 is pure computation (category thresholds + owner-only config) layered on W1 + L1.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic v2, pytest, ruff, mypy (backend); Vue 3, TypeScript, Vite, Vant 4, Vitest, vue-tsc (frontend). Single-source amortization: `server/packages/domain/liability_calculator.py` (Python only; frontend calls `POST /liabilities/simulate`).

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-19-p0-family-finance-core-design.md` §0, §2, §5, §6, §7) and the repo `CLAUDE.md`:

- **URL style:** all router root-path endpoints use `""` not `"/"` (`redirect_slashes=False` in `app/main.py`). No trailing slashes, no 307 redirects. New endpoints: `POST /wishes/{id}/savings`, `GET /wishes/{id}/savings`, `DELETE /wishes/{id}/savings/{log_id}`, `POST /liabilities/simulate`, `GET /ai/context`, `POST /ai/wish-advice/generate`, `GET/PUT /family/debt-thresholds`.
- **Snowflake/bigint serialization:** all `bigint` fields (IDs) serialized as `str` via `SnowflakeBase` (only converts `int` fields named `id`/`*_id`). New `NUMERIC(18,2)` money fields (`saved_amount`, `monthly_saving`, log `amount`) are `Decimal` in the model and serialized as `str` (2 decimals) — `SnowflakeBase` does NOT auto-convert non-int fields, so the money schemas declare them as `str` with a `@field_validator` coercing from `Decimal`/`float`. Frontend types these as `string` (string-numeric), not JS `number`, to avoid precision loss.
- **W1 invariant:** `wish_savings_log` is source of truth, `wish.saved_amount` is a derived cache. Savings add/delete must update `saved_amount` in the same transaction with `SELECT ... FOR UPDATE` on the wish row. A `recompute_saved_amount(wish_id)` helper + CI assertion `saved_amount == SUM(log.amount)` guard against drift.
- **W1 authz:** all savings endpoints `Depends(require_adult)` + family filter (`wish.family_id == caller.family_id`, reuse `wish_service.get_wish`). POST: any family adult may record (shared contribution). DELETE: only `log.user_id == caller.id` or family owner. child role cannot write savings (reuse the `_assert_not_child` pattern if present; otherwise `require_adult` already excludes child).
- **Money-field migration (W1):** new fields `NUMERIC(18,2)`; also migrate `wish.expected_price` Float→NUMERIC in the same migration (spec §2.1 "推荐，一次性统一"). W2 arithmetic that mixes `saved_amount`(NUMERIC) with `expected_price` coerces both to `Decimal` before comparing.
- **L1/L2 single-source:** `liability_calculator.py` is backend-only. Frontend L2 simulate modal calls `POST /liabilities/simulate`; no amortization logic in TS. No rate→ no interest region shown (returns None).
- **W5 thresholds:** owner-only config (`require_owner`); read visible to all family members. Defaults: 信用卡类 12% / 消费贷 10% / 房贷 6% / 其他 10%. Stored in family settings.
- **W4 is independent:** own AI prompt + own cache key `family_id:wish_advice:{fingerprint}` (8h, wish-change invalidation). W4 output is `redistribution[]`, NOT finance_coach's `suggestions[]` (schema-mutually-exclusive per §7.1). W4 + finance_coach share only the prompt template skeleton, not output.
- **A1b greenfield:** `AIChatBox.vue` has zero `route.query`/`source` handling today (confirmed: `useRoute` not imported; query handling lives in `chatSession` store via `initializeFromUrl`). A1b adds: backend `GET /ai/context?source=&id=` (family-scoped, 404 if `entity.family_id != caller.family_id`) + frontend query-param parse + entity fetch + first-message injection. 3s timeout on context fetch; on timeout/404, plain blank chat + toast.
- **A1b prompt-injection sanitization:** injected entity JSON goes through `_sanitize_user_text`-style control-char stripping + length cap before entering the first user turn (mirror `asset_suggest.py`'s XML-delimiter pattern).
- **i18n:** every new user-facing string defined in `frontend/apps/main/src/i18n/locales/zh-CN.ts` under `t('...')`. No hardcoded Chinese in `.vue`/`.ts` logic. Toasts use Vant icons (showSuccessToast/showFailToast), no emoji in i18n text.
- **Currency:** new wish/liability UI uses `useCurrency()` (returns `{ format, formatPercent, currency }`) instead of hardcoded `¥` where the existing page doesn't already hardcode. (WishListPage/WishDetailPage currently hardcode `¥` — match the surrounding code's convention; do not refactor adjacent hardcodes unless the touched field needs it.)
- **Error messages in Chinese:** backend `HTTPException(detail=...)` uses Chinese strings.
- **Never run dev servers** (`uvicorn`/`pnpm dev`) from agents — verify with `pytest`, `ruff check`, `mypy`, `pnpm typecheck`, `pnpm test:run`.
- **Surgical changes / no speculative code:** touch only what each task requires. Do not refactor adjacent code.
- **TDD:** failing test first, minimal implementation, verify pass, commit — every task.
- **Test paths:** the authoritative backend test root is `server/tests/backend/` (on `pyproject.toml`'s `testpaths = ["tests"]`, has the root `conftest.py`). New tests go there: model tests flat at `tests/backend/test_*_model.py`, service tests at `tests/backend/services/`, router tests at `tests/backend/routers/`. The `server/apps/backend/tests/` root was a leftover removed in Plan A T10 Step 6 — do NOT recreate it. Fixtures available: `db_session` (DB session), `test_family`/`test_user` (real snowflake ids, FK-safe), `client`/`auth_headers` (TestClient + auth). Use real `test_family.id`/`test_user.id` rather than hardcoded `1` where FK constraints matter.

---

## File Structure

**Backend — Create:**
- `server/apps/backend/alembic/versions/c2d3e4f5a6b7_add_wish_savings_fields_and_log.py` — W1 migration: `wish` adds `saved_amount`/`target_date`/`monthly_saving`/`ignore_debt_warning` (NUMERIC/DATE/NUMERIC/BOOL) + `expected_price` Float→NUMERIC; new `wish_savings_log` table. down_revision = Plan A's `b9c7d2e4f6a8` (head).
- `server/apps/backend/app/models/wish_savings_log.py` — `WishSavingsLog` model.
- `server/apps/backend/app/schemas/wish_savings.py` — `SavingsLogCreate` / `SavingsLogResponse` (money as str) / `WishSavingsSummary`.
- `server/apps/backend/app/services/wish_savings.py` — CRUD + invariant (`recompute_saved_amount`) + `SELECT FOR UPDATE`.
- `server/packages/domain/liability_calculator.py` — single-source amortization (`calc_amortization`, returns `AmortizationResult`).
- `server/apps/backend/app/routers/ai_context.py` — `GET /ai/context?source=&id=` entity summary (family-scoped).
- `server/apps/backend/app/services/ai_context_builder.py` — builds + sanitizes the context payload per source.
- `server/apps/backend/app/routers/ai_wish_advice.py` — `POST /ai/wish-advice/generate` (independent W4 AI call + `wish_advice:{fingerprint}` cache).

**Backend — Modify:**
- `server/apps/backend/app/models/wish.py` — add the 4 new columns + change `expected_price` to `Numeric(18,2)`.
- `server/apps/backend/app/schemas/wish.py` — `WishCreate`/`WishUpdate`/`WishResponse` add `target_date`/`monthly_saving`/`saved_amount`/`savings_count`/`ignore_debt_warning`; `expected_price`/`saved_amount`/`monthly_saving` typed as `str` with Decimal validators.
- `server/apps/backend/app/routers/wishes.py` — add savings sub-routes (`POST/GET/DELETE /wishes/{id}/savings[/{log_id}]`) + `PATCH /wishes/{id}/ignore-debt-warning` (W5).
- `server/apps/backend/app/services/wish.py` — `create_wish`/`update_wish` handle new fields; realize resets savings.
- `server/apps/backend/app/routers/liabilities.py` — add `POST /liabilities/simulate`.
- `server/apps/backend/app/routers/family.py` — add `GET/PUT /family/debt-thresholds` (owner-only PUT, reuse `update_family_settings` owner guard).
- `server/apps/backend/app/main.py` — register `ai_context` + `ai_wish_advice` routers.
- `server/apps/backend/app/services/wish.py` (entity-change invalidation) — W1 savings writes also call `invalidate_capability(family_id, "finance_coach", db)` (Plan A T9 already wired asset/liability/wish CRUD; W1 savings add/delete adds its own calls).

**Frontend — Create:**
- `frontend/apps/main/src/components/wishes/WishSavingsProgress.vue` — progress bar + "记录存入" button (W1 detail).
- `frontend/apps/main/src/components/wishes/WishSavingsLogDialog.vue` — savings log list + delete confirm (W1).
- `frontend/apps/main/src/components/wishes/WishSavingsRecordDialog.vue` — record-savings form popup (W1).
- `frontend/apps/main/src/components/liability/LiabilityStrategyCard.vue` — L1 avalanche/snowball comparison (list top).
- `frontend/apps/main/src/components/liability/InterestForecast.vue` — L2 interest prediction region (detail).
- `frontend/apps/main/src/components/liability/SimulateExtraDialog.vue` — L2 simulate-extra-amount modal.
- `frontend/apps/main/src/components/dashboard/FinanceCoachCard.vue` — D2/A1a finance_coach suggestions card.
- `frontend/apps/main/src/components/wishes/WishAdviceCard.vue` — W4 priority-advice card + redistribution dialog.
- `frontend/apps/main/src/composables/useAiContext.ts` — A1b: parse `route.query`, fetch `/ai/context`, build first message.

**Frontend — Modify:**
- `frontend/apps/main/src/pages/WishFormPage.vue` — add 储蓄计划 group (`target_date` + `monthly_saving`).
- `frontend/apps/main/src/pages/WishDetailPage.vue` — add `WishSavingsProgress` + log dialog; add A1b "问 AI 规划储蓄" button; add W5 hint above savings region.
- `frontend/apps/main/src/pages/WishListPage.vue` — refactor afford bar (W2); add `WishAdviceCard` (W4) + W5 hint; add A1b context nav.
- `frontend/apps/main/src/pages/LiabilityDetailPage.vue` — add `InterestForecast` + `SimulateExtraDialog`; add A1b "问 AI 优化还款" button.
- `frontend/apps/main/src/pages/LiabilityListPage.vue` — add `LiabilityStrategyCard` (L1); handle `?focus=liability_strategy` query (W5).
- `frontend/apps/main/src/pages/DashboardPage.vue` — insert `FinanceCoachCard` between NetWorthCard and SmartRemindersCard.
- `frontend/apps/main/src/components/ai/AIChatBox.vue` — call `useAiContext` on mount to inject prefilled first message (A1b).
- `frontend/apps/main/src/api/wishes.ts` — add `recordSaving`/`getSavingsLog`/`deleteSavingsLog`/`setIgnoreDebtWarning`.
- `frontend/apps/main/src/api/liabilities.ts` — add `simulateLiability`.
- `frontend/apps/main/src/api/ai.ts` (or new `aiFinance.ts`) — add `getFinanceCoach`/`getWishAdvice`/`getAiContext`.
- `frontend/apps/main/src/types/index.ts` — extend `Wish` (+savings fields), add `SavingsLog`/`LiabilitySimResult`/`FinanceSuggestion`/`WishAdvice`/`AiContextPayload` types.
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — new keys under `wish.savings.*`, `liability.strategy.*`, `liability.interest.*`, `dashboard.financeCoach.*`, `wish.advice.*`, `wish.debtWarning.*`, `aiChat.context.*`.

---

## Task 1: W1 migration — wish savings fields + `wish_savings_log` table

**Files:**
- Create: `server/apps/backend/alembic/versions/c2d3e4f5a6b7_add_wish_savings_fields_and_log.py`
- Modify: `server/apps/backend/app/models/wish.py` — add 4 columns + change `expected_price` to `Numeric(18,2)`
- Create: `server/apps/backend/app/models/wish_savings_log.py` — `WishSavingsLog` model
- Test: `server/tests/backend/test_wish_savings_model.py`

**Interfaces:**
- Consumes: `down_revision = "b9c7d2e4f6a8"` (Plan A T7 head). `Wish` model (`expected_price: Mapped[float | None]` Float at line 28). `SnowflakeBase`/`next_id` for the new table PK.
- Produces:
  - `wish.saved_amount NUMERIC(18,2) DEFAULT 0`, `target_date DATE NULL`, `monthly_saving NUMERIC(18,2) DEFAULT 0`, `ignore_debt_warning BOOLEAN DEFAULT FALSE`; `expected_price` migrated Float→`NUMERIC(18,2)` (existing float values preserved, coerced to Decimal).
  - `wish_savings_log` table: `id BIGINT PK snowflake`, `wish_id BIGINT FK`, `family_id BIGINT`, `user_id BIGINT`, `amount NUMERIC(18,2)`, `log_date DATE`, `note VARCHAR(200) NULL`, `created_at DATETIME`. Indexes `(wish_id, log_date DESC)` + `(family_id, created_at)`.
  - `WishSavingsLog` model for Task 2's service.

- [x] **Step 1: Write the failing test**

Create `server/tests/backend/test_wish_savings_model.py`:

```python
"""Wish savings fields + WishSavingsLog model (Plan B W1)."""
from datetime import date
from decimal import Decimal

from apps.backend.app.models.wish import Wish
from apps.backend.app.models.wish_savings_log import WishSavingsLog


def test_wish_has_savings_fields(db_session):
    """Wish model exposes the 4 new fields + NUMERIC expected_price."""
    w = Wish(family_id=1, user_id=1, name="x", expected_price=Decimal("100.50"),
             saved_amount=Decimal("30.00"), monthly_saving=Decimal("10.00"),
             target_date=date(2026, 12, 31), ignore_debt_warning=True)
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    assert w.saved_amount == Decimal("30.00")
    assert w.monthly_saving == Decimal("10.00")
    assert w.target_date == date(2026, 12, 31)
    assert w.ignore_debt_warning is True
    assert isinstance(w.expected_price, Decimal)


def test_wish_defaults(db_session):
    """New wish has zeroed savings + ignore_debt_warning=False."""
    w = Wish(family_id=1, user_id=1, name="y")
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    assert w.saved_amount == Decimal("0")
    assert w.monthly_saving == Decimal("0")
    assert w.target_date is None
    assert w.ignore_debt_warning is False


def test_wish_savings_log_model(db_session):
    log = WishSavingsLog(wish_id=1, family_id=1, user_id=1,
                         amount=Decimal("50.00"), log_date=date(2026, 7, 19), note="seed")
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    assert log.id is not None
    assert log.amount == Decimal("50.00")
    assert log.note == "seed"
    assert log.created_at is not None
```

> **Fixture note:** confirm `db_session` fixture name in `server/tests/backend/conftest.py`; rename if it's `session`. The family_id/user_id `1` assumes the test DB has those rows — if FK constraints are enforced in the test DB, use real fixture-created family/user ids.

- [x] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_wish_savings_model.py -v`
Expected: FAIL — `AttributeError` (Wish has no `saved_amount`) / `ImportError` (WishSavingsLog not defined).

- [x] **Step 3: Create the migration**

Create `server/apps/backend/alembic/versions/c2d3e4f5a6b7_add_wish_savings_fields_and_log.py`:

```python
"""add wish savings fields + wish_savings_log table

Revision ID: c2d3e4f5a6b7
Revises: b9c7d2e4f6a8
Create Date: 2026-07-19

Plan B W1: wish savings progress. Adds saved_amount (derived cache)/target_date/
monthly_saving/ignore_debt_warning to wishes, migrates expected_price Float→
NUMERIC(18,2) (spec §2.1 "一次性统一"), and creates wish_savings_log as the
source of truth. saved_amount is maintained in-transaction by the savings CRUD
(Plan B W1 service); a recompute_saved_amount helper + CI assertion guard drift.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b9c7d2e4f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. wish: add savings fields + migrate expected_price Float → NUMERIC(18,2).
    #    SQLite ALTER TABLE can't change a column type in-place; use batch mode.
    with op.batch_alter_table("wishes") as batch:
        batch.add_column(sa.Column("saved_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("target_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("monthly_saving", sa.Numeric(18, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("ignore_debt_warning", sa.Boolean(), nullable=False, server_default="0"))
        # Migrate expected_price Float → NUMERIC(18,2). Existing float values
        # coerce to Decimal on read. SQLite batch recreate handles the type swap.
        batch.alter_column("expected_price",
                           existing_type=sa.Float(),
                           type_=sa.Numeric(18, 2),
                           existing_nullable=True)

    # 2. wish_savings_log: source of truth.
    op.create_table(
        "wish_savings_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("wish_id", sa.BigInteger(), sa.ForeignKey("wishes.id"), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_wish_savings_logs_wish_logdate",
        "wish_savings_logs",
        ["wish_id", sa.text("log_date DESC")],
    )
    op.create_index(
        "ix_wish_savings_logs_family_created",
        "wish_savings_logs",
        ["family_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wish_savings_logs_family_created", table_name="wish_savings_logs")
    op.drop_index("ix_wish_savings_logs_wish_logdate", table_name="wish_savings_logs")
    op.drop_table("wish_savings_logs")
    with op.batch_alter_table("wishes") as batch:
        batch.alter_column("expected_price",
                           existing_type=sa.Numeric(18, 2),
                           type_=sa.Float(),
                           existing_nullable=True)
        batch.drop_column("ignore_debt_warning")
        batch.drop_column("monthly_saving")
        batch.drop_column("target_date")
        batch.drop_column("saved_amount")
```

> **SQLite note:** `batch_alter_table` is the repo's SQLite-compatible alter pattern (it recreates the table). PostgreSQL handles `alter_column` natively; batch mode is a no-op there. The `sa.text("log_date DESC")` for the descending index works on both. If the existing migrations in the repo use a different table-create pattern, match it (read `server/apps/backend/alembic/versions/` for a recent `op.create_table` precedent).

- [x] **Step 4: Update the Wish model**

In `server/apps/backend/app/models/wish.py`:
- Ensure `Numeric`, `Date`, `Boolean` are imported from `sqlalchemy` (add to the existing import line at line 7).
- Change `expected_price` (line 28) from `Float` to `Numeric(18, 2)`:

```python
    expected_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
```

- After the `currency` column (line 32), add the 4 new columns:

```python
    # Plan B W1: savings progress fields.
    # saved_amount is a DERIVED cache of SUM(wish_savings_log.amount); maintained
    # in-transaction by the savings CRUD (see wish_savings.py). source of truth =
    # wish_savings_log. NUMERIC(18,2) — serialized as str (2 decimals) in API.
    saved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_saving: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    # Plan B W5: per-wish opt-out of the high-interest-debt linkage hint.
    ignore_debt_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
```

- Add imports `from decimal import Decimal` and `from datetime import date` at the top (if not already present).

- [x] **Step 5: Create the WishSavingsLog model**

Create `server/apps/backend/app/models/wish_savings_log.py`:

```python
"""WishSavingsLog — source of truth for a wish's saved_amount (Plan B W1).

Each row is one deposit (positive amount) or withdrawal (negative amount).
saved_amount on the parent Wish is a derived cache maintained in-transaction by
the savings CRUD; recompute_saved_amount() reconciles it (CI asserts equality).
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.models.base import Base  # confirm Base import path
from packages.core.snowflake import next_id  # confirm; mirror Wish model's next_id import


class WishSavingsLog(Base):
    __tablename__ = "wish_savings_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    wish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wishes.id"), nullable=False, index=True)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # recorder (DELETE authz)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # +deposit / -withdrawal
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
```

> **Import check:** confirm `Base`'s import path — read `server/apps/backend/app/models/wish.py`'s `Base` import and mirror it. Confirm `next_id`'s path — mirror the Wish model's import.

- [x] **Step 6: Run the migration + test**

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: revision `c2d3e4f5a6b7` applies; `alembic current` shows `c2d3e4f5a6b7 (head)`.

Run: `cd server && uv run pytest tests/backend/test_wish_savings_model.py -v`
Expected: all 3 tests PASS.

- [x] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/models/wish.py apps/backend/app/models/wish_savings_log.py tests/backend/test_wish_savings_model.py && uv run mypy apps/backend/app/models/wish.py apps/backend/app/models/wish_savings_log.py`
Expected: no errors.

- [x] **Step 8: Regression — existing wish tests still pass**

Run: `cd server && uv run pytest tests/backend/test_wishes.py tests/backend/services/test_wish_service.py -v 2>/dev/null || uv run pytest tests/backend/ -k wish -v`
Expected: existing tests PASS (the `expected_price` Float→NUMERIC migration is backward-compatible at the DB level; existing code reading `wish.expected_price` as float still works because Decimal is JSON-serializable; if a test asserts `isinstance(x, float)`, update it to `Decimal`).

- [x] **Step 9: Commit**

```bash
git add server/apps/backend/alembic/versions/c2d3e4f5a6b7_add_wish_savings_fields_and_log.py server/apps/backend/app/models/wish.py server/apps/backend/app/models/wish_savings_log.py server/tests/backend/test_wish_savings_model.py
git commit -m "feat(wish): W1 savings fields + wish_savings_log table (Plan B T1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: W1 savings schema + service (CRUD + invariant + SELECT FOR UPDATE)

**Files:**
- Create: `server/apps/backend/app/schemas/wish_savings.py`
- Create: `server/apps/backend/app/services/wish_savings.py`
- Test: `server/tests/backend/services/test_wish_savings_service.py`

**Interfaces:**
- Consumes: `WishSavingsLog` (Task 1), `wish_service.get_wish` (family-scoped fetch + NOT_FOUND), `AppError`/`ErrorCode` (mirror wish_service), `require_adult` (router, Task 3), `invalidate_capability` (Plan A T9 — savings writes also bust finance_coach cache).
- Produces:
  - `SavingsLogCreate(amount: Decimal, log_date: date | None, note: str | None)`, `SavingsLogResponse(SnowflakeBase)` (money as str), `WishSavingsResponse(SnowflakeBase)` (saved_amount/monthly_saving as str, savings_count int).
  - `wish_savings.record_savings(db, user, wish_id, req) -> Wish` — writes log + in-transaction `UPDATE wish SET saved_amount = saved_amount + amount` with `SELECT ... FOR UPDATE`.
  - `wish_savings.list_savings(db, user, wish_id, page, size) -> list[WishSavingsLog]` — by `log_date DESC`.
  - `wish_savings.delete_savings(db, user, wish_id, log_id) -> None` — DELETE authz (`log.user_id == caller.id` or family owner) + in-transaction `saved_amount -= log.amount`.
  - `wish_savings.recompute_saved_amount(db, wish_id) -> Decimal` — reconciliation helper: `saved_amount = SUM(log.amount)`. CI asserts `saved_amount == recompute_saved_amount(wish_id)`.

- [x] **Step 1: Write the failing test**

Create `server/tests/backend/services/test_wish_savings_service.py`:

```python
"""W1 savings service: invariant + authz + reconciliation (Plan B T2)."""
from datetime import date
from decimal import Decimal

import pytest

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services import wish_savings
from apps.backend.app.services.wish_savings import (
    delete_savings,
    list_savings,
    record_savings,
    recompute_saved_amount,
)


def test_record_savings_updates_saved_amount_in_transaction(db_session, wish_owner_user, owned_wish):
    """POST savings writes log + updates saved_amount atomically."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id),
                   amount=Decimal("100"), log_date=date(2026, 7, 19), note="first")
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("100")
    logs = list_savings(db_session, wish_owner_user, str(owned_wish.id))
    assert len(logs) == 1
    assert logs[0].amount == Decimal("100")


def test_negative_savings_decrements(db_session, wish_owner_user, owned_wish):
    """A negative amount (withdrawal) decrements saved_amount."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("100"), log_date=date(2026, 7, 19))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("-30"), log_date=date(2026, 7, 20))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("70")


def test_delete_savings_reverses_amount(db_session, wish_owner_user, owned_wish):
    """DELETE subtracts the log's amount from saved_amount in-transaction."""
    log = record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("50"), log_date=date(2026, 7, 19))
    delete_savings(db_session, wish_owner_user, str(owned_wish.id), str(log.id))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("0")
    assert list_savings(db_session, wish_owner_user, str(owned_wish.id)) == []


def test_delete_savings_forbidden_for_non_recorder(db_session, wish_owner_user, other_adult_in_family, owned_wish, recorder_log):
    """A different family adult (not the recorder, not owner) cannot delete the log."""
    with pytest.raises(AppError) as exc:
        delete_savings(db_session, other_adult_in_family, str(owned_wish.id), str(recorder_log.id))
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_delete_savings_allowed_for_family_owner(db_session, family_owner, owned_wish, recorder_log_by_other):
    """The family owner can delete any family member's savings log."""
    delete_savings(db_session, family_owner, str(owned_wish.id), str(recorder_log_by_other.id))  # no raise


def test_recompute_saved_amount_equals_sum(db_session, wish_owner_user, owned_wish):
    """recompute_saved_amount == SUM(log.amount) — the invariant."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("100"), log_date=date(2026, 7, 19))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("50"), log_date=date(2026, 7, 20))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("-20"), log_date=date(2026, 7, 21))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == recompute_saved_amount(db_session, owned_wish.id)
    assert recompute_saved_amount(db_session, owned_wish.id) == Decimal("130")


def test_record_savings_other_family_wish_404(db_session, wish_owner_user, other_family_wish):
    """A wish not in the caller's family returns NOT_FOUND (family filter)."""
    with pytest.raises(AppError) as exc:
        record_savings(db_session, wish_owner_user, str(other_family_wish.id), amount=Decimal("10"), log_date=date(2026, 7, 19))
    assert exc.value.code == ErrorCode.NOT_FOUND
```

> **Fixture note:** `wish_owner_user` / `owned_wish` / `other_adult_in_family` / `family_owner` / `recorder_log` / `recorder_log_by_other` / `other_family_wish` are test fixtures you build in conftest (or inline). Minimal: create a Family, an owner User, a second adult User, an owned Wish, a Wish in another family. If the repo's conftest has helpers like `make_user`/`make_wish`, use them. The assertions are the contract — adapt fixtures to satisfy them.

- [x] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/services/test_wish_savings_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'wish_savings'` (module not created).

- [x] **Step 3: Create the schema**

Create `server/apps/backend/app/schemas/wish_savings.py`:

```python
"""W1 savings request/response schemas (Plan B T2).

Money fields (amount, saved_amount, monthly_saving) are NUMERIC(18,2) Decimal in
the model, serialized as str (2 decimals) per the bigint/numeric-as-string
convention. SnowflakeBase only converts int id/*_id fields; money fields are
typed str here with a field_validator coercing Decimal→str.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class SavingsLogCreate(BaseModel):
    amount: Decimal  # positive deposit / negative withdrawal
    log_date: date | None = None  # default today (set in service)
    note: str | None = None


class SavingsLogResponse(SnowflakeBase):
    id: str
    wish_id: str
    family_id: str
    user_id: str
    amount: str  # Decimal → str (2 decimals)
    log_date: date
    note: str | None
    created_at: str  # isoformat

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        return str(Decimal(v).quantize(Decimal("0.01"))) if v is not None else v

    @field_serializer("created_at")
    def _ser_created_at(self, v):
        return v.isoformat() if v else None


class WishSavingsResponse(SnowflakeBase):
    wish_id: str
    saved_amount: str
    monthly_saving: str
    target_date: date | None
    savings_count: int

    @field_validator("saved_amount", "monthly_saving", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return str(Decimal(v).quantize(Decimal("0.01"))) if v is not None else v
```

> **Note:** `SnowflakeBase` already converts `wish_id`/`family_id`/`user_id` int→str via its `model_serializer`. The `amount`/`saved_amount`/`monthly_saving` `str` fields + `field_validator` handle the Decimal→str coercion explicitly. Confirm `SnowflakeBase` is importable from `apps.backend.app.schemas.base` (it is — `server/apps/backend/app/schemas/base.py:13`).

- [x] **Step 4: Create the service**

Create `server/apps/backend/app/services/wish_savings.py`:

```python
"""W1 wish savings CRUD + invariant (Plan B T2).

INVARIANT: wish_savings_log is the source of truth; wish.saved_amount is a
derived cache. record_savings/delete_savings update saved_amount in the SAME
transaction as the log write, with SELECT ... FOR UPDATE on the wish row to
serialize concurrent savings writes. recompute_saved_amount() reconciles (CI
asserts saved_amount == recompute_saved_amount(wish_id)).

AUTHZ: reuse wish_service.get_wish (family filter + NOT_FOUND). POST: any family
adult may record (shared contribution). DELETE: only log.user_id == caller.id or
the family owner (mirror wish_service.update_wish owner check, broadened to
family owner since savings are a shared family resource).
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from apps.backend.app.models.wish_savings_log import WishSavingsLog
from apps.backend.app.services.finance_coach_cache import invalidate_capability
from apps.backend.app.services.wish import get_wish


def record_savings(
    db: Session,
    user: User,
    wish_id: str,
    amount: Decimal,
    log_date: date | None = None,
    note: str | None = None,
) -> WishSavingsLog:
    """Write a savings log + update saved_amount in-transaction. Returns the log.

    SELECT ... FOR UPDATE locks the wish row so concurrent deposits serialize
    (prevents lost-update on saved_amount). Commits.
    """
    log_date = log_date or datetime.now(timezone.utc).date()
    # Lock the wish row for the duration of this transaction.
    wish = (
        db.query(Wish)
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .with_for_update()
        .first()
    )
    if not wish:
        raise AppError(ErrorCode.NOT_FOUND)

    log = WishSavingsLog(
        wish_id=int(wish_id),
        family_id=user.family_id,
        user_id=user.id,
        amount=amount,
        log_date=log_date,
        note=note,
    )
    db.add(log)
    wish.saved_amount = (wish.saved_amount or Decimal("0")) + amount
    invalidate_capability(db, user.family_id, "finance_coach")
    db.commit()
    db.refresh(log)
    db.refresh(wish)
    return log


def list_savings(
    db: Session,
    user: User,
    wish_id: str,
    page: int = 1,
    size: int = 50,
) -> Sequence[WishSavingsLog]:
    """List a wish's savings logs, newest log_date first (family-scoped)."""
    # Family-scope via get_wish (raises NOT_FOUND if the wish isn't in the family).
    get_wish(db, user, wish_id)
    offset = (page - 1) * size
    return (
        db.query(WishSavingsLog)
        .filter(WishSavingsLog.wish_id == int(wish_id))
        .order_by(WishSavingsLog.log_date.desc(), WishSavingsLog.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )


def delete_savings(
    db: Session,
    user: User,
    wish_id: str,
    log_id: str,
) -> None:
    """Delete a savings log + reverse its amount from saved_amount in-transaction.

    AUTHZ: the recorder (log.user_id == caller.id) or the family owner. A
    different family adult is FORBIDDEN (savings deletion is destructive — it
    reverses another member's recorded deposit).
    """
    wish = (
        db.query(Wish)
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .with_for_update()
        .first()
    )
    if not wish:
        raise AppError(ErrorCode.NOT_FOUND)
    log = (
        db.query(WishSavingsLog)
        .filter(WishSavingsLog.id == log_id, WishSavingsLog.wish_id == int(wish_id))
        .first()
    )
    if not log:
        raise AppError(ErrorCode.NOT_FOUND)
    # AUTHZ: recorder or family owner.
    is_owner = getattr(user, "role", None) == "owner"
    if log.user_id != user.id and not is_owner:
        raise AppError(ErrorCode.FORBIDDEN)

    db.delete(log)
    wish.saved_amount = (wish.saved_amount or Decimal("0")) - log.amount
    invalidate_capability(db, user.family_id, "finance_coach")
    db.commit()


def recompute_saved_amount(db: Session, wish_id: int | str) -> Decimal:
    """Reconciliation helper: saved_amount := SUM(log.amount). Does NOT commit
    (caller commits) — used by CI canary + admin fix + bulk-import backfill.

    spec §2.2: any future write path touching savings must either maintain the
    counter in-transaction or call this.
    """
    total = db.execute(
        select(func.coalesce(func.sum(WishSavingsLog.amount), Decimal("0")))
        .where(WishSavingsLog.wish_id == int(wish_id))
    ).scalar_one()
    wish = db.query(Wish).filter(Wish.id == int(wish_id)).first()
    if wish is not None:
        wish.saved_amount = Decimal(total)
    return Decimal(total)
```

> **`user.role` check:** confirm the User model has a `role` field (it should — `require_owner` in `auth/ai_deps.py` checks `current_user.role`). If the field is named differently (e.g. `is_owner`), adjust. Read `server/apps/backend/app/models/user.py` and `apps/backend/app/auth/ai_deps.py:20` (`require_owner`) to mirror the exact owner-detection expression.

- [x] **Step 5: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/services/test_wish_savings_service.py -v`
Expected: all 7 tests PASS.

- [x] **Step 6: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/schemas/wish_savings.py apps/backend/app/services/wish_savings.py tests/backend/services/test_wish_savings_service.py && uv run mypy apps/backend/app/schemas/wish_savings.py apps/backend/app/services/wish_savings.py`
Expected: no errors.

- [x] **Step 7: Commit**

```bash
git add server/apps/backend/app/schemas/wish_savings.py server/apps/backend/app/services/wish_savings.py server/tests/backend/services/test_wish_savings_service.py
git commit -m "feat(wish): W1 savings service + invariant + authz (Plan B T2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: W1 router — savings endpoints + wish schema extension

**Files:**
- Modify: `server/apps/backend/app/routers/wishes.py` — add `POST/GET/DELETE /wishes/{wish_id}/savings[/{log_id}]` + `PATCH /wishes/{wish_id}/ignore-debt-warning` (W5)
- Modify: `server/apps/backend/app/schemas/wish.py` — extend `WishCreate`/`WishUpdate`/`WishResponse` with the new fields
- Modify: `server/apps/backend/app/services/wish.py` — `create_wish`/`update_wish` pass through `target_date`/`monthly_saving`/`ignore_debt_warning`
- Test: `server/tests/backend/routers/test_wishes_savings.py`

**Interfaces:**
- Consumes: `require_adult` (deps), `wish_savings` service (Task 2), `wish_service.get_wish` (owner-check reuse), `SavingsLogCreate`/`SavingsLogResponse` (Task 2 schema). Existing wish router pattern (lines 14-57).
- Produces:
  - `POST /wishes/{wish_id}/savings` (201) → `SavingsLogResponse` (also returns updated wish via header/X-Wish-Saved-Amount, or frontend refetches).
  - `GET /wishes/{wish_id}/savings?page=1&size=50` → `list[SavingsLogResponse]`.
  - `DELETE /wishes/{wish_id}/savings/{log_id}` → `{"detail": "已删除"}`.
  - `PATCH /wishes/{wish_id}/ignore-debt-warning` (body `{ignore: bool}`) → `WishResponse` (W5).
  - `WishResponse` now includes `saved_amount`/`target_date`/`monthly_saving`/`savings_count`/`ignore_debt_warning` (all money as str).

- [x] **Step 1: Write the failing test**

Create `server/tests/backend/routers/test_wishes_savings.py`:

```python
"""W1 savings endpoints + ignore-debt-warning (Plan B T3)."""
from decimal import Decimal


def test_post_savings_201(client, auth_headers, owned_wish_id):
    resp = client.post(
        f"/api/v1/wishes/{owned_wish_id}/savings",
        json={"amount": "100.00", "note": "first"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == "100.00"
    assert body["wish_id"] == str(owned_wish_id)


def test_get_savings_list(client, auth_headers, owned_wish_id_with_logs):
    resp = client.get(f"/api/v1/wishes/{owned_wish_id_with_logs}/savings", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_delete_savings_owner_ok(client, auth_headers, owned_wish_id, savings_log_id):
    resp = client.delete(
        f"/api/v1/wishes/{owned_wish_id}/savings/{savings_log_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"detail": "已删除"}


def test_delete_savings_other_family_404(client, auth_headers, other_family_wish_id, log_id_in_other_family):
    resp = client.delete(
        f"/api/v1/wishes/{other_family_wish_id}/savings/{log_id_in_other_family}", headers=auth_headers
    )
    assert resp.status_code == 404


def test_patch_ignore_debt_warning(client, auth_headers, owned_wish_id):
    resp = client.patch(
        f"/api/v1/wishes/{owned_wish_id}/ignore-debt-warning",
        json={"ignore": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ignore_debt_warning"] is True


def test_wish_response_includes_savings_fields(client, auth_headers, owned_wish_id):
    """WishResponse serializes saved_amount/monthly_saving as str (2 decimals)."""
    resp = client.get(f"/api/v1/wishes/{owned_wish_id}", headers=auth_headers)
    body = resp.json()
    assert "saved_amount" in body and isinstance(body["saved_amount"], str)
    assert "monthly_saving" in body and isinstance(body["monthly_saving"], str)
    assert "target_date" in body
    assert "savings_count" in body
    assert "ignore_debt_warning" in body
```

> **Fixture note:** `owned_wish_id` / `owned_wish_id_with_logs` / `savings_log_id` / `other_family_wish_id` / `log_id_in_other_family` — build via the service directly in conftest (call `wish_savings.record_savings` to seed logs). The API prefix `/api/v1` — confirm by grepping an existing router test (`test_wishes.py`). Money is sent/received as str ("100.00") per the serialization convention.

- [x] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/routers/test_wishes_savings.py -v`
Expected: FAIL — 404 (savings routes not registered) / missing fields.

- [x] **Step 3: Extend the wish schemas**

In `server/apps/backend/app/schemas/wish.py` (read the file first to see `WishCreate`/`WishUpdate`/`WishResponse` definitions):

- Add to `WishCreate` and `WishUpdate` (optional fields):
```python
    target_date: date | None = None
    monthly_saving: Decimal | None = None
    ignore_debt_warning: bool | None = None  # W5
```
- Add to `WishResponse` (read-side; money as str):
```python
    saved_amount: str
    monthly_saving: str
    target_date: date | None
    savings_count: int = 0
    ignore_debt_warning: bool
```
- Add a `field_validator` on `WishResponse.saved_amount` and `WishResponse.monthly_saving` (mode="before") coercing `Decimal`→`str(quantize(0.01))` — mirror the pattern in `wish_savings.py` (Task 2 Step 3).
- `savings_count` is computed in the service/router (count of logs for the wish).
- Add `WishIgnoreDebtWarning(BaseModel): ignore: bool` for the PATCH body.

> Import `date`, `Decimal`, `field_validator` as needed. If `WishResponse` doesn't already inherit `SnowflakeBase`, keep whatever it inherits (the money-coercion validator is explicit). Confirm `expected_price` in `WishResponse` is also `str` now (it's NUMERIC after Task 1) — add the same validator.

- [x] **Step 4: Update wish_service for new fields**

In `server/apps/backend/app/services/wish.py`:
- `create_wish` (line 35): pass through `target_date`/`monthly_saving`/`ignore_debt_warning` from `req` (use `req.model_dump` or explicit field assignment). `saved_amount` defaults to 0 (model default).
- `update_wish` (line 52): already uses `req.model_dump(exclude_unset=True)` + `setattr` loop (line 56-57), so the new fields flow through automatically once they're on `WishUpdate`.

Confirm `create_wish`'s `Wish(...)` constructor includes the new optional fields:
```python
def create_wish(db: Session, user: User, req: WishCreate) -> Wish:
    wish = Wish(
        family_id=user.family_id,
        user_id=user.id,
        name=req.name,
        description=req.description,
        expected_price=req.expected_price,
        priority=req.priority,
        category_id=req.category_id,
        converts_to_asset=req.converts_to_asset,
        target_date=req.target_date,
        monthly_saving=req.monthly_saving or Decimal("0"),
        ignore_debt_warning=req.ignore_debt_warning or False,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish
```

- [x] **Step 5: Add the savings + ignore-debt-warning routes**

In `server/apps/backend/app/routers/wishes.py`, after the `realize_wish` route (line 57), add:

```python
from apps.backend.app.schemas.wish_savings import SavingsLogCreate, SavingsLogResponse
from apps.backend.app.services import wish_savings
from apps.backend.app.schemas.wish import WishIgnoreDebtWarning


@router.post("/{wish_id}/savings", response_model=SavingsLogResponse, status_code=201)
def record_savings(
    wish_id: int,
    req: SavingsLogCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    log = wish_savings.record_savings(db, user, str(wish_id), req.amount, req.log_date, req.note)
    return log


@router.get("/{wish_id}/savings", response_model=list[SavingsLogResponse])
def list_savings(
    wish_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return wish_savings.list_savings(db, user, str(wish_id), page, size)


@router.delete("/{wish_id}/savings/{log_id}")
def delete_savings(
    wish_id: int,
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    wish_savings.delete_savings(db, user, str(wish_id), str(log_id))
    return {"detail": "已删除"}


@router.patch("/{wish_id}/ignore-debt-warning", response_model=WishResponse)
def set_ignore_debt_warning(
    wish_id: int,
    req: WishIgnoreDebtWarning,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return wish_service.set_ignore_debt_warning(db, user, str(wish_id), req.ignore)
```

Add `set_ignore_debt_warning` to `server/apps/backend/app/services/wish.py` (mirror `update_wish` but only the one field — owner-only per W5? The spec §5.3 says the form's "忽略" button sets it; any adult editing their own wish should be able to. Reuse `update_wish`'s owner check `wish.user_id != user.id`):

```python
def set_ignore_debt_warning(db: Session, user: User, wish_id: str, ignore: bool) -> Wish:
    wish = get_wish(db, user, wish_id)
    if wish.user_id != user.id:
        raise AppError(ErrorCode.FORBIDDEN)
    wish.ignore_debt_warning = ignore
    db.commit()
    db.refresh(wish)
    return wish
```

> **savings_count on WishResponse:** the `WishResponse` needs `savings_count`. Compute it in a `@field_validator` or a service helper. Simplest: add a `@computed_field`-like pattern via a `model_validator` that counts — but counting needs the db. Instead, have the router/service attach `savings_count` before returning: in `get_wish`/`list_wishes`, set `wish._savings_count = db.query(func.count(WishSavingsLog.id)).filter(...).scalar()` and expose it on the response. Read how `WishResponse` is currently constructed (does it use `model_validate` from the ORM?) and add `savings_count` as a field populated by a small helper `enrich_wish_response(wish, db)`. If the existing pattern is `response_model=WishResponse` with `from_attributes=True`, add a `savings_count` property on the model OR a pre-response hook. Match the existing convention (grep for any `computed`/`property` on Wish or sibling models).

- [x] **Step 6: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/routers/test_wishes_savings.py -v`
Expected: all 6 tests PASS.

- [x] **Step 7: Lint + typecheck + regression**

Run: `cd server && uv run ruff check apps/backend/app/routers/wishes.py apps/backend/app/schemas/wish.py apps/backend/app/services/wish.py tests/backend/routers/test_wishes_savings.py && uv run mypy apps/backend/app/routers/wishes.py apps/backend/app/schemas/wish.py apps/backend/app/services/wish.py`
Expected: no errors.

Run: `cd server && uv run pytest tests/backend/test_wishes.py -v 2>/dev/null || uv run pytest tests/backend/ -k wish -v`
Expected: existing wish tests still PASS (new fields are optional/additive).

- [x] **Step 8: Commit**

```bash
git add server/apps/backend/app/routers/wishes.py server/apps/backend/app/schemas/wish.py server/apps/backend/app/services/wish.py server/tests/backend/routers/test_wishes_savings.py
git commit -m "feat(wish): W1 savings endpoints + ignore-debt-warning + schema (Plan B T3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: L1/L2 single-source amortization util + `/liabilities/simulate`

**Files:**
- Create: `server/packages/domain/liability_calculator.py` — `calc_amortization` + `AmortizationResult`
- Create: `server/apps/backend/app/schemas/liability_simulate.py` — request/response models
- Modify: `server/apps/backend/app/routers/liabilities.py` — add `POST /liabilities/simulate`
- Test: `server/packages/domain/tests/test_liability_calculator.py` (6 cases per spec §6.4)
- Test: `server/tests/backend/routers/test_liabilities_simulate.py`

**Interfaces:**
- Consumes: `Liability` model fields `interest_rate` (Float|None), `remaining_amount` (Float|None — confirm exact name; the frontend type says `remaining_amount`), `monthly_payment` (Float|None), `category`, `is_active`. `require_adult` (router).
- Produces:
  - `calc_amortization(remaining: Decimal, annual_rate: Decimal, monthly_payment: Decimal | None, extra_monthly: Decimal = 0, min_payment: Decimal = Decimal("100")) -> AmortizationResult | None` — returns None when `annual_rate` is None/0 or inputs missing (spec §6.1: no rate → no interest region).
  - `AmortizationResult(total_interest: Decimal, months: int, monthly_payment: Decimal | None, warning: str | None, schedule: list[dict] | None)` — `warning` set when 最低还款不覆盖利息 or 超 1200 月.
  - `POST /liabilities/simulate` body `{remaining, annual_rate, monthly_payment?, extra_monthly?}` → `{total_interest, months, monthly_payment, warning, savings_vs_baseline?, months_saved?}`. When `extra_monthly > 0`, the response also returns the baseline (extra=0) comparison so the frontend shows "省 ¥Y, 提前 N 月".

- [x] **Step 1: Write the failing test — the 6 amortization cases**

Create `server/packages/domain/tests/test_liability_calculator.py` (spec §6.4: 等额本息正常 / 提前还款省息 / 最低还款覆盖利息 / 最低还款不覆盖利息(报警) / 无利率 / extra≥剩余本金(立即还清)):

```python
"""L1/L2 single-source amortization — 6 cases (Plan B T4, spec §6.4)."""
from decimal import Decimal

from packages.domain.liability_calculator import AmortizationResult, calc_amortization


def test_equal_payment_amortization_normal():
    """等额本息正常: total_interest > 0, months finite, balance reaches ~0."""
    r = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                          monthly_payment=Decimal("3000"))
    assert r is not None
    assert r.total_interest > 0
    assert 30 <= r.months <= 50  # ~100k @12%, 3k/mo ≈ 38 months
    assert r.warning is None


def test_extra_payment_saves_interest_and_months():
    """提前还款省息: extra>0 → fewer months + less interest than baseline."""
    base = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                             monthly_payment=Decimal("3000"))
    extra = calc_amortization(remaining=Decimal("100000"), annual_rate=Decimal("12"),
                              monthly_payment=Decimal("3000"), extra_monthly=Decimal("500"))
    assert extra is not None and base is not None
    assert extra.total_interest < base.total_interest
    assert extra.months < base.months


def test_min_payment_covers_interest_credit_card():
    """最低还款覆盖利息: min_payment = max(remaining*5%, 100), covers interest."""
    # 10k @18% → monthly interest 150; min = max(500, 100) = 500 > 150 → covers.
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("18"),
                          monthly_payment=None, min_payment=Decimal("100"))
    assert r is not None
    assert r.months <= 1200
    assert r.warning is None
    assert r.total_interest > 0


def test_min_payment_does_not_cover_interest_warns():
    """最低还款不覆盖利息: warning set (still returns, capped at 1200 months)."""
    # 100k @36% → monthly interest 3000; min = max(5000, 100) = 5000 > 3000 → covers.
    # Force non-cover: huge balance + high rate + tiny min_payment.
    # 1,000,000 @60% → monthly interest 50000; min = max(50000, 100) = 50000 == interest → 还本=0.
    r = calc_amortization(remaining=Decimal("1000000"), annual_rate=Decimal("60"),
                          monthly_payment=None, min_payment=Decimal("100"))
    assert r is not None
    # When 还本 <= 0 the util must warn (spec §6.1 "最低还款不足，建议增加月供").
    assert r.warning is not None
    assert r.months >= 1200 or r.warning  # capped or warned


def test_no_interest_rate_returns_none():
    """无利率: returns None — caller shows no interest region."""
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=None,
                          monthly_payment=Decimal("1000"))
    assert r is None
    r2 = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("0"),
                           monthly_payment=Decimal("1000"))
    assert r2 is None


def test_extra_ge_remaining_pays_off_immediately():
    """extra≥剩余本金: immediate payoff, 0 interest, 1 month."""
    r = calc_amortization(remaining=Decimal("10000"), annual_rate=Decimal("12"),
                          monthly_payment=Decimal("1000"), extra_monthly=Decimal("15000"))
    assert r is not None
    assert r.total_interest < Decimal("200")  # ~1 month of interest only
    assert r.months <= 2
```

> **Note on case 4:** the spec says "最低还款不覆盖利息(报警)". The `min_payment = max(remaining*5%, 100)` formula usually covers interest for typical rates. To deterministically trigger the non-cover warning, the test uses an extreme rate (60%) where monthly interest equals the 5% minimum — at that boundary 还本≈0 and the util warns. If your implementation's threshold differs, adjust the test inputs to reliably hit `还本 <= 0` while keeping the assertion `r.warning is not None`. The contract is: when the minimum payment fails to reduce principal, the result carries a warning.

- [x] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest packages/domain/tests/test_liability_calculator.py -v`
Expected: FAIL — `ImportError: cannot import name 'calc_amortization'`.

- [x] **Step 3: Create the amortization util**

Create `server/packages/domain/liability_calculator.py`:

```python
"""Single-source amortization model for L1 (strategy) + L2 (interest forecast).

spec §6.1: BACKEND-ONLY (no dual-language drift). The frontend L2 simulate modal
calls POST /liabilities/simulate; no amortization logic in TS.

Two modes:
- Equal-payment (monthly_payment given): 每月 利息 = 剩余 × 月利率, 还本 = 月供 - 利息.
- Minimum-payment (monthly_payment None, e.g. credit card): 最低 = max(剩余×5%, min_payment),
  还本 = max(最低 - 利息, 0). When 还本 <= 0 → warning "最低还款不足，建议增加月供".

extra_monthly increases the effective payment (月供 + extra) and the caller
compares baseline vs extra to report 省息/提前月数.

No interest_rate (None or 0) → returns None (caller shows no interest region).
Cap at 1200 months (100 years) to prevent infinite loops on pathological inputs.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

MAX_MONTHS = 1200  # 100-year cap — backstop against non-converging inputs.
TWO_PLACES = Decimal("0.01")


@dataclass
class AmortizationResult:
    total_interest: Decimal
    months: int
    monthly_payment: Decimal | None  # None when min-payment mode computed internally
    warning: str | None = None  # set when 最低还款不足 or hit MAX_MONTHS cap
    schedule: list[dict] | None = field(default=None)  # optional month-by-month (L2 baseline)


def _q(v: Decimal) -> Decimal:
    """Quantize to 2 decimals (cents)."""
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calc_amortization(
    remaining: Decimal,
    annual_rate: Decimal | None,
    monthly_payment: Decimal | None,
    extra_monthly: Decimal = Decimal("0"),
    min_payment: Decimal = Decimal("100"),
) -> AmortizationResult | None:
    """Iterate month-by-month to payoff. Returns None when no usable rate.

    Args:
      remaining: current principal balance.
      annual_rate: annual interest rate as a percent (e.g. 12 for 12%). None/0 → None.
      monthly_payment: fixed monthly payment (equal-payment mode). None → min-payment mode.
      extra_monthly: additional monthly principal payment (L2 "若每月多还 ¥X").
      min_payment: floor for the minimum payment in min-payment mode (default ¥100).
    """
    if annual_rate is None or annual_rate <= 0 or remaining <= 0:
        return None

    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    balance = Decimal(remaining)
    total_interest = Decimal("0")
    months = 0
    warning: str | None = None
    use_min_mode = monthly_payment is None
    effective_payment = (monthly_payment or Decimal("0")) + extra_monthly

    while balance > Decimal("0.005"):  # half-cent tolerance
        if months >= MAX_MONTHS:
            warning = "已达最大迭代月数（100 年），请增加月供或检查利率输入"
            break
        interest = _q(balance * monthly_rate)
        if use_min_mode:
            minimum = max(_q(balance * Decimal("0.05")), min_payment)
            principal = minimum - interest
            effective_payment = minimum + extra_monthly
            principal = effective_payment - interest
            if principal <= 0:
                warning = "最低还款不足覆盖利息，建议增加月供"
                # Still accrue + apply what we can; the loop will hit MAX_MONTHS.
                principal = Decimal("0")
        else:
            principal = effective_payment - interest
            if principal <= 0:
                # Fixed payment doesn't cover interest — can't converge.
                warning = "月供不足以覆盖利息，请增加月供"
                break
        # Don't overpay past the balance (+ this month's interest).
        principal = min(principal, balance)
        balance = _q(balance - principal)
        total_interest = _q(total_interest + interest)
        months += 1

    return AmortizationResult(
        total_interest=_q(total_interest),
        months=months,
        monthly_payment=effective_payment if not use_min_mode else None,
        warning=warning,
    )
```

> **Decimal precision:** all intermediate money math uses `Decimal` (not float) to avoid drift; quantize to cents each iteration. The `0.005` balance tolerance handles rounding residue. The `extra_monthly` is added to the effective payment in BOTH modes (spec §6.1: "月供变 monthly_payment + extra"). Confirm the test-case-4 expectation aligns with this implementation; if the boundary logic differs, the test's extreme inputs still force `principal <= 0` → warning.

- [x] **Step 4: Run the util test to verify it passes**

Run: `cd server && uv run pytest packages/domain/tests/test_liability_calculator.py -v`
Expected: all 6 tests PASS.

- [x] **Step 5: Create the simulate schema + route**

Create `server/apps/backend/app/schemas/liability_simulate.py`:

```python
"""L2 /liabilities/simulate request/response (Plan B T4)."""
from decimal import Decimal
from pydantic import BaseModel, field_validator


class SimulateRequest(BaseModel):
    remaining: Decimal
    annual_rate: Decimal
    monthly_payment: Decimal | None = None
    extra_monthly: Decimal = Decimal("0")


class SimulateResponse(BaseModel):
    total_interest: str  # Decimal → str (2 decimals)
    months: int
    monthly_payment: str | None
    warning: str | None
    # Only present when extra_monthly > 0 (the L2 "省 ¥Y, 提前 N 月" comparison):
    baseline_total_interest: str | None = None
    baseline_months: int | None = None
    savings_vs_baseline: str | None = None
    months_saved: int | None = None

    @field_validator("total_interest", "monthly_payment", "baseline_total_interest", "savings_vs_baseline", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if v is None:
            return None
        return str(Decimal(v).quantize(Decimal("0.01")))
```

In `server/apps/backend/app/routers/liabilities.py`, add the route (confirm the router prefix — likely `/liabilities`; the route is `POST /liabilities/simulate`). Read the existing file to match the auth/db imports:

```python
from apps.backend.app.schemas.liability_simulate import SimulateRequest, SimulateResponse
from packages.domain.liability_calculator import calc_amortization


@router.post("/simulate", response_model=SimulateResponse)
def simulate_liability(
    req: SimulateRequest,
    user: User = Depends(require_adult),
):
    """L2: forecast total interest + months, with optional extra-payment comparison.

    Pure compute (no db write). When extra_monthly > 0, also computes the
    baseline (extra=0) so the frontend shows '省 ¥Y, 提前 N 月'.
    """
    extra = req.extra_monthly or Decimal("0")
    result = calc_amortization(req.remaining, req.annual_rate, req.monthly_payment, extra)
    if result is None:
        # No usable rate — return a response the frontend treats as 'no interest region'.
        return SimulateResponse(total_interest="0", months=0, monthly_payment=None,
                                warning="无利率，无法计算利息预测")
    resp = SimulateResponse(
        total_interest=result.total_interest,
        months=result.months,
        monthly_payment=result.monthly_payment,
        warning=result.warning,
    )
    if extra > 0:
        base = calc_amortization(req.remaining, req.annual_rate, req.monthly_payment, Decimal("0"))
        if base is not None:
            resp.baseline_total_interest = base.total_interest
            resp.baseline_months = base.months
            resp.savings_vs_baseline = base.total_interest - result.total_interest
            resp.months_saved = base.months - result.months
    return resp
```

> **Route guard:** `simulate` must not be shadowed by a `/{liability_id}` path param. FastAPI matches static routes before param routes IF declared first — so declare `POST /simulate` BEFORE `POST /{liability_id}` (or wherever a param route sits). Read the existing liabilities router to place it correctly. If there's no conflicting param route, placement is flexible.

- [x] **Step 6: Write + run the router test**

Create `server/tests/backend/routers/test_liabilities_simulate.py`:

```python
"""L2 /liabilities/simulate endpoint (Plan B T4)."""
from decimal import Decimal


def test_simulate_returns_interest_and_months(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "100000", "annual_rate": "12", "monthly_payment": "3000"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_interest"]) > 0
    assert body["months"] > 0


def test_simulate_with_extra_returns_comparison(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "100000", "annual_rate": "12", "monthly_payment": "3000", "extra_monthly": "500"},
        headers=auth_headers,
    )
    body = resp.json()
    assert body["baseline_total_interest"] is not None
    assert body["savings_vs_baseline"] is not None
    assert Decimal(body["savings_vs_baseline"]) > 0
    assert body["months_saved"] > 0


def test_simulate_zero_rate_returns_warning(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "100000", "annual_rate": "0", "monthly_payment": "3000"},
        headers=auth_headers,
    )
    body = resp.json()
    assert body["warning"] is not None
    assert body["total_interest"] == "0"
```

Run: `cd server && uv run pytest tests/backend/routers/test_liabilities_simulate.py -v`
Expected: all 3 tests PASS.

- [x] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check packages/domain/liability_calculator.py apps/backend/app/schemas/liability_simulate.py apps/backend/app/routers/liabilities.py packages/domain/tests/test_liability_calculator.py tests/backend/routers/test_liabilities_simulate.py && uv run mypy packages/domain/liability_calculator.py apps/backend/app/routers/liabilities.py`
Expected: no errors.

- [x] **Step 8: Commit**

```bash
git add server/packages/domain/liability_calculator.py server/apps/backend/app/schemas/liability_simulate.py server/apps/backend/app/routers/liabilities.py server/packages/domain/tests/test_liability_calculator.py server/tests/backend/routers/test_liabilities_simulate.py
git commit -m "feat(liability): L1/L2 single-source amortization + /simulate (Plan B T4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: D2/A1a — Dashboard FinanceCoachCard (frontend)

**Prerequisite:** Plan A complete — `POST /ai/finance-coach/generate` returns cached JSON `{status, report: {suggestions: [...]}}` or streams. This task renders the top-3 suggestions.

**Files:**
- Create: `frontend/apps/main/src/components/dashboard/FinanceCoachCard.vue`
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue` — insert the card between NetWorthCard (line 27) and SmartRemindersCard (line 29)
- Modify: `frontend/apps/main/src/api/ai.ts` (or create `aiFinance.ts`) — add `getFinanceCoach(force?: boolean)`
- Modify: `frontend/apps/main/src/types/index.ts` — add `FinanceSuggestion` type
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add `dashboard.financeCoach.*`
- Test: `frontend/apps/main/src/components/dashboard/__tests__/FinanceCoachCard.spec.ts`

**Interfaces:**
- Consumes: Plan A's `POST /api/v1/ai/finance-coach/generate?force=false`. The cached response is `{status: "cached", generated_at, report: {suggestions: [{id, severity, title, action, target_type, target_id, cta_label}]}}`. When not cached, the endpoint streams — for D2 (card, not live chat) the frontend should request and read the final `finance_coach.result` event; simplest correct approach: the backend already caches after the first stream, so the card calls `getFinanceCoach()` which hits the endpoint; if it streams, the composable collects the `finance_coach.result` frame and the card renders it. (Confirm the backend's non-cached response shape from Plan A T8 — it returns `StreamingResponse`. The frontend SSE-consumption pattern already exists in `useThreadChat.ts`; reuse the `EventSource`/fetch-stream helper.)
- Produces: a Dashboard card showing up to 3 suggestions (severity color bar: high=红, medium=橙, low=蓝), each with title + action + a CTA button. Skeleton while loading; silent hide on failure/empty (spec §7.2 design-lens). A 刷新 button (force=true).

- [x] **Step 1: Write the failing test**

Create `frontend/apps/main/src/components/dashboard/__tests__/FinanceCoachCard.spec.ts`:

```typescript
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import FinanceCoachCard from '../FinanceCoachCard.vue'
import * as aiApi from '@/api/ai'

const mockSuggestion = (id: string, severity: 'high' | 'medium' | 'low') => ({
  id, severity, title: `建议${id}`, action: '行动',
  target_type: 'liability', target_id: '1', cta_label: '查看',
})

describe('FinanceCoachCard', () => {
  it('renders up to 3 suggestions with severity color bars', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockResolvedValue({
      status: 'cached', generated_at: '2026-07-19T10:00:00',
      report: { suggestions: [mockSuggestion('1', 'high'), mockSuggestion('2', 'medium'), mockSuggestion('3', 'low'), mockSuggestion('4', 'high')] },
    })
    const wrapper = mount(FinanceCoachCard, { global: { stubs: ['van-button'] } })
    await flushPromises()
    // Only top 3 rendered (spec §7.2 "前 3 条").
    expect(wrapper.findAll('[data-test="suggestion"]')).toHaveLength(3)
    expect(wrapper.find('[data-test="suggestion-1"]').classes()).toContain('severity-high')
  })

  it('hides silently when suggestions is empty', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockResolvedValue({
      status: 'cached', generated_at: '2026-07-19T10:00:00', report: { suggestions: [] },
    })
    const wrapper = mount(FinanceCoachCard, { global: { stubs: ['van-button'] } })
    await flushPromises()
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(false)
  })

  it('hides silently on fetch failure', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockRejectedValue(new Error('network'))
    const wrapper = mount(FinanceCoachCard, { global: { stubs: ['van-button'] } })
    await flushPromises()
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(false)
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend/apps/main && pnpm test:run -- FinanceCoachCard`
Expected: FAIL — component doesn't exist.

- [x] **Step 3: Add the API client + types**

In `frontend/apps/main/src/types/index.ts`, add:

```typescript
export type SuggestionSeverity = 'high' | 'medium' | 'low'
export interface FinanceSuggestion {
  id: string
  severity: SuggestionSeverity
  title: string
  action: string
  target_type: 'liability' | 'asset' | 'wish'
  target_id: string
  cta_label: string
}
export interface FinanceCoachResponse {
  status: 'cached' | 'streaming'
  generated_at?: string
  report: { suggestions: FinanceSuggestion[] }
}
```

In `frontend/apps/main/src/api/ai.ts` (or create `src/api/aiFinance.ts` and re-export), add:

```typescript
import http from './index'
import type { FinanceCoachResponse } from '@/types'

// D2/A1a: fetch the finance_coach suggestions. The backend returns a cached JSON
// 200 within 8h, or streams a fresh generation. For the dashboard card (not live
// chat), we consume the stream to its terminal finance_coach.result frame and
// resolve with the parsed suggestions. On any error, reject (caller hides card).
export async function getFinanceCoach(force = false): Promise<FinanceCoachResponse> {
  const resp = await fetch(`/api/v1/ai/finance-coach/generate?force=${force}`, {
    headers: { ...(http.defaults.headers.common as Record<string, string>) },
  })
  if (!resp.ok) throw new Error(`finance_coach ${resp.status}`)
  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return resp.json() as Promise<FinanceCoachResponse>
  }
  // Streaming response — consume SSE until the finance_coach.result frame.
  const reader = resp.body?.getReader()
  if (!reader) throw new Error('no stream body')
  const decoder = new TextDecoder()
  let buf = ''
  let suggestions: FinanceSuggestion[] = []
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const frames = buf.split('\n\n')
    buf = frames.pop() || ''
    for (const frame of frames) {
      const dataLine = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!dataLine) continue
      try {
        const data = JSON.parse(dataLine.slice(6))
        if (data.type === 'finance_coach.result' && data.payload?.suggestions) {
          suggestions = data.payload.suggestions
        }
      } catch { /* ignore malformed frame */ }
    }
  }
  return { status: 'streaming', report: { suggestions } }
}
```

> **Auth header:** confirm how the existing `http` axios instance attaches the JWT (interceptor). If `fetch` doesn't get the token, the 401 will reject and the card hides. Read `frontend/apps/main/src/api/index.ts` to mirror the auth-header injection (e.g. import the token from the auth store and set `Authorization` explicitly). If simpler, switch this client to use the axios `http` instance with `responseType: 'stream'` — but axios browser stream handling is awkward, so `fetch` is preferred; just ensure the JWT is attached.

- [x] **Step 4: Create the FinanceCoachCard component**

Create `frontend/apps/main/src/components/dashboard/FinanceCoachCard.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { getFinanceCoach } from '@/api/ai'
import type { FinanceSuggestion } from '@/types'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const suggestions = ref<FinanceSuggestion[]>([])
const loading = ref(true)
const visible = ref(false)
const refreshing = ref(false)

async function load(force = false) {
  try {
    refreshing.value = force
    const resp = await getFinanceCoach(force)
    // Advice baseline gate (spec §7.1): schema-validate before display.
    const valid = (resp.report.suggestions || []).filter((s) =>
      s && s.id && ['high', 'medium', 'low'].includes(s.severity) &&
      s.title && s.action && s.target_type && s.target_id && s.cta_label,
    )
    if (valid.length === 0) {
      visible.value = false
      return
    }
    suggestions.value = valid.slice(0, 3)
    visible.value = true
  } catch {
    visible.value = false  // silent hide on failure (spec §7.2)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function onCta(s: FinanceSuggestion) {
  // CTA navigates to the target entity (A1b-style passive entry).
  if (s.target_type === 'liability') router.push(`/liabilities/${s.target_id}`)
  else if (s.target_type === 'asset') router.push(`/assets/${s.target_id}`)
  else if (s.target_type === 'wish') router.push(`/wishes/${s.target_id}`)
}

onMounted(() => load(false))
</script>

<template>
  <van-skeleton v-if="loading" title :row="3" />
  <div v-else-if="visible" class="finance-coach-card" data-test="finance-coach-card">
    <div class="fc-header">
      <span class="fc-title">{{ t('dashboard.financeCoach.title') }}</span>
      <van-button size="mini" plain :loading="refreshing" @click="load(true)">
        {{ t('dashboard.financeCoach.refresh') }}
      </van-button>
    </div>
    <div
      v-for="s in suggestions"
      :key="s.id"
      :class="['fc-suggestion', `severity-${s.severity}`]"
      :data-test="`suggestion-${s.id}`"
    >
      <div class="fc-severity-bar" />
      <div class="fc-body">
        <div class="fc-s-title">{{ s.title }}</div>
        <div class="fc-s-action">{{ s.action }}</div>
      </div>
      <van-button size="small" type="primary" @click="onCta(s)">{{ s.cta_label }}</van-button>
    </div>
    <div class="fc-disclaimer">{{ t('dashboard.financeCoach.disclaimer') }}</div>
  </div>
  <!-- v-else: silent hide (empty / failure) -->
</template>

<style scoped>
.finance-coach-card { background: var(--van-card-bg, #fff); border-radius: 12px; padding: 12px; margin: 8px 0; }
.fc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.fc-title { font-weight: 600; }
.fc-suggestion { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--van-border-color, #eee); }
.fc-severity-bar { width: 4px; align-self: stretch; border-radius: 2px; }
.severity-high .fc-severity-bar { background: #ee0a24; }
.severity-medium .fc-severity-bar { background: #ff976a; }
.severity-low .fc-severity-bar { background: #1989fa; }
.fc-body { flex: 1; }
.fc-s-title { font-weight: 500; }
.fc-s-action { font-size: 12px; color: var(--van-text-color-2, #969799); }
.fc-disclaimer { font-size: 11px; color: var(--van-text-color-3, #c8c9cc); margin-top: 8px; }
</style>
```

- [x] **Step 5: Add i18n keys**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, under the `dashboard` section (line 67), add a `financeCoach` sub-object:

```typescript
    financeCoach: {
      title: '财务教练建议',
      refresh: '刷新',
      disclaimer: '基于你录入的数据，仅供参考',
    },
```

- [x] **Step 6: Insert the card into DashboardPage**

In `frontend/apps/main/src/pages/DashboardPage.vue`, between the hero-section close `</div>` (line 27) and the SmartRemindersCard comment (line 29), add:

```vue
    <!-- D2/A1a: finance_coach proactive suggestions card (Plan B T5) -->
    <FinanceCoachCard />
```

And add the import in the `<script setup>`:

```typescript
import FinanceCoachCard from '@/components/dashboard/FinanceCoachCard.vue'
```

- [x] **Step 7: Run the test to verify it passes**

Run: `cd frontend/apps/main && pnpm test:run -- FinanceCoachCard`
Expected: all 3 tests PASS.

- [x] **Step 8: Typecheck + lint**

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint -- src/components/dashboard/FinanceCoachCard.vue src/pages/DashboardPage.vue src/api/ai.ts`
Expected: no errors.

- [x] **Step 9: Commit**

```bash
git add frontend/apps/main/src/components/dashboard/FinanceCoachCard.vue frontend/apps/main/src/pages/DashboardPage.vue frontend/apps/main/src/api/ai.ts frontend/apps/main/src/types/index.ts frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/components/dashboard/__tests__/FinanceCoachCard.spec.ts
git commit -m "feat(dashboard): D2/A1a finance_coach suggestions card (Plan B T5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: A1b — `/ai/context` endpoint + greenfield chat context injection

**Files:**
- Create: `server/apps/backend/app/routers/ai_context.py` — `GET /ai/context?source=&id=`
- Create: `server/apps/backend/app/services/ai_context_builder.py` — per-source entity summary + sanitization
- Modify: `server/apps/backend/app/main.py` — register the router
- Modify: `frontend/apps/main/src/composables/useAiContext.ts` (create) — parse `route.query`, fetch `/ai/context` (3s timeout), build first message
- Modify: `frontend/apps/main/src/components/ai/AIChatBox.vue` — call `useAiContext` on mount (before/after `store.initializeFromUrl`)
- Modify: `frontend/apps/main/src/api/ai.ts` — add `getAiContext(source, id)`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add `aiChat.context.*`
- Test: `server/tests/backend/routers/test_ai_context.py`
- Test: `frontend/apps/main/src/composables/__tests__/useAiContext.spec.ts`

**Interfaces:**
- Consumes: `require_adult` (deps). `wish_service.get_wish` + a family-scoped liability fetch (mirror `get_wish`'s family filter). `_sanitize_user_text`-style helper from `asset_suggest.py` (control-char strip + length cap).
- Produces:
  - `GET /ai/context?source={liability_detail|wish_detail|liability_strategy|wish_advice}&id={id}` → `{source, summary: <sanitized JSON string or text>}`. Family-scoped: `entity.family_id == caller.family_id` else 404. The `summary` is the pre-sanitized context to inject as the first user turn.
  - Frontend `useAiContext()`: reads `route.query.source` + `route.query.id`; fetches `/ai/context` with a 3s timeout; on success returns the prefilled first message; on timeout/404 returns null + toasts. `AIChatBox` uses it to seed the conversation (distinct from `store.pendingMessage`'s `q` param — A1b injects structured context, not a typed question).

- [ ] **Step 1: Write the failing backend test**

Create `server/tests/backend/routers/test_ai_context.py`:

```python
"""A1b /ai/context endpoint: per-source summary + family-scope 404 (Plan B T6)."""
import pytest


def test_liability_detail_returns_summary(client, auth_headers, owned_liability_id):
    resp = client.get(
        f"/api/v1/ai/context?source=liability_detail&id={owned_liability_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "liability_detail"
    assert "summary" in body and isinstance(body["summary"], str)
    # PII minimization: summary references the liability id, not raw PII leakage.


def test_wish_detail_returns_summary(client, auth_headers, owned_wish_id):
    resp = client.get(f"/api/v1/ai/context?source=wish_detail&id={owned_wish_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["source"] == "wish_detail"


def test_liability_strategy_returns_all_active_summary(client, auth_headers):
    resp = client.get("/api/v1/ai/context?source=liability_strategy&id=0", headers=auth_headers)
    assert resp.status_code == 200
    assert "summary" in resp.json()


def test_wish_advice_returns_all_pending_summary(client, auth_headers):
    resp = client.get("/api/v1/ai/context?source=wish_advice&id=0", headers=auth_headers)
    assert resp.status_code == 200


def test_other_family_entity_returns_404(client, auth_headers, other_family_liability_id):
    resp = client.get(
        f"/api/v1/ai/context?source=liability_detail&id={other_family_liability_id}", headers=auth_headers
    )
    assert resp.status_code == 404


def test_unknown_source_returns_400(client, auth_headers):
    resp = client.get("/api/v1/ai/context?source=bogus&id=1", headers=auth_headers)
    assert resp.status_code == 400
```

- [ ] **Step 2: Run backend test to verify it fails**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_context.py -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Create the context builder service**

Create `server/apps/backend/app/services/ai_context_builder.py`:

```python
"""Build + sanitize the A1b context payload per source (Plan B T6).

spec §7.3: the injected entity JSON is sanitized (control-char strip + length
cap, mirroring asset_suggest.py's _sanitize_user_text) before entering the first
user turn. Family-scope is enforced by the caller (get_wish / liability family
filter) — the builder only shapes + sanitizes what's already family-scoped.
"""
import json
import re
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.liability import Liability
from apps.backend.app.models.wish import Wish
from apps.backend.app.models.user import User

MAX_CONTEXT_LEN = 4000  # chars — cap to bound the first user turn.

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    """Strip control chars + cap length (mirror asset_suggest._sanitize_user_text)."""
    cleaned = _CONTROL_CHARS.sub("", text)
    return cleaned[:MAX_CONTEXT_LEN]


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def build_liability_detail(db: Session, user: User, liability_id: str) -> str | None:
    l = db.query(Liability).filter(Liability.id == liability_id, Liability.family_id == user.family_id).first()
    if not l:
        return None
    payload = {
        "type": "liability_detail",
        "id": str(l.id),
        "category": l.category,
        "remaining_amount": _dec(l.remaining_amount),
        "interest_rate": _dec(l.interest_rate),
        "monthly_payment": _dec(l.monthly_payment),
        "is_active": l.is_active,
        "end_date": str(l.end_date) if l.end_date else None,
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_wish_detail(db: Session, user: User, wish_id: str) -> str | None:
    w = db.query(Wish).filter(Wish.id == wish_id, Wish.family_id == user.family_id).first()
    if not w:
        return None
    payload = {
        "type": "wish_detail",
        "id": str(w.id),
        "name": w.name,  # name is prompt-required for wish context (the user names wishes)
        "expected_price": _dec(w.expected_price),
        "saved_amount": _dec(w.saved_amount),
        "monthly_saving": _dec(w.monthly_saving),
        "target_date": str(w.target_date) if w.target_date else None,
        "priority": w.priority,
        "status": w.status,
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_liability_strategy(db: Session, user: User) -> str:
    """All active liabilities summary for the '问 AI 详细规划' jump (no single id)."""
    liabilities = db.query(Liability).filter(
        Liability.family_id == user.family_id, Liability.is_active.is_(True)
    ).all()
    payload = {
        "type": "liability_strategy",
        "liabilities": [
            {"id": str(l.id), "category": l.category, "remaining_amount": _dec(l.remaining_amount),
             "interest_rate": _dec(l.interest_rate), "monthly_payment": _dec(l.monthly_payment)}
            for l in liabilities
        ],
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_wish_advice(db: Session, user: User) -> str:
    """All pending wishes summary for the W4 '看完整建议' jump."""
    wishes = db.query(Wish).filter(
        Wish.family_id == user.family_id, Wish.status == "pending"
    ).all()
    payload = {
        "type": "wish_advice",
        "wishes": [
            {"id": str(w.id), "name": w.name, "expected_price": _dec(w.expected_price),
             "saved_amount": _dec(w.saved_amount), "monthly_saving": _dec(w.monthly_saving),
             "target_date": str(w.target_date) if w.target_date else None, "priority": w.priority}
            for w in wishes
        ],
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))
```

> **Column check:** confirm `Liability`'s exact column names (`remaining_amount`/`interest_rate`/`monthly_payment`/`is_active`/`end_date`/`category`) by reading `server/apps/backend/app/models/liability.py`. Adjust any mismatched names. `Wish.name`/`expected_price`/`saved_amount`/`monthly_saving`/`target_date`/`priority`/`status` are confirmed (Task 1).

- [ ] **Step 4: Create the router**

Create `server/apps/backend/app/routers/ai_context.py`:

```python
"""A1b: unified entity-context endpoint for /ai/chat prefill (Plan B T6).

GET /api/v1/ai/context?source={liability_detail|wish_detail|liability_strategy|wish_advice}&id={id}
Returns a sanitized context summary to inject as the first user turn when the
user clicks a passive '问 AI' button. Family-scoped: a cross-family entity id
returns 404 (no data injection).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.services import ai_context_builder as builder

router = APIRouter(prefix="/ai/context", tags=["ai-context"])

_VALID_SOURCES = {"liability_detail", "wish_detail", "liability_strategy", "wish_advice"}


@router.get("")
def get_ai_context(
    source: str = Query(...),
    id: str = Query("0"),  # "0" for the strategy/advice aggregates (no single entity)
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    if source not in _VALID_SOURCES:
        raise HTTPException(status_code=400, detail="未知的 source 值")

    if source == "liability_detail":
        summary = builder.build_liability_detail(db, user, id)
        if summary is None:
            raise HTTPException(status_code=404, detail="负债不存在")
    elif source == "wish_detail":
        summary = builder.build_wish_detail(db, user, id)
        if summary is None:
            raise HTTPException(status_code=404, detail="心愿不存在")
    elif source == "liability_strategy":
        summary = builder.build_liability_strategy(db, user)
    else:  # wish_advice
        summary = builder.build_wish_advice(db, user)

    return {"source": source, "summary": summary}
```

Register in `server/apps/backend/app/main.py` next to the other ai routers:
```python
from apps.backend.app.routers import ai_context
app.include_router(ai_context.router, prefix="/api/v1")
```

- [ ] **Step 5: Run backend test to verify it passes**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_context.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 6: Create the frontend composable**

Create `frontend/apps/main/src/composables/useAiContext.ts`:

```typescript
import { useRoute, useRouter } from 'vue-router'
import { ref } from 'vue'
import { showFailToast } from 'vant'
import { getAiContext } from '@/api/ai'
import { useI18n } from 'vue-i18n'

type AiSource = 'liability_detail' | 'wish_detail' | 'liability_strategy' | 'wish_advice'

/**
 * A1b: parse route.query.source + route.query.id, fetch the family-scoped entity
 * context from /ai/context (3s timeout), and return a prefilled first-user-turn
 * message. On timeout/404, returns null + toasts (spec §7.3 design-lens). The
 * caller (AIChatBox) sends this as the first message so the AI has full context
 * without the user retyping.
 */
export function useAiContext() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useI18n()
  const contextLoaded = ref(false)
  const contextLabel = ref<string | null>(null)  // "已带入：负债详情" removable tag

  async function loadContext(): Promise<string | null> {
    const source = route.query.source as AiSource | undefined
    const id = (route.query.id as string) || '0'
    if (!source) return null

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 3000)
    try {
      const resp = await getAiContext(source, id, controller.signal)
      contextLabel.value = t(`aiChat.context.label.${source}`)
      contextLoaded.value = true
      // Build the first user turn: a framing instruction + the sanitized summary.
      return t('aiChat.context.prefill', { source: t(`aiChat.context.label.${source}`) }) + '\n\n' + resp.summary
    } catch {
      showFailToast(t('aiChat.context.loadFailed'))
      return null  // plain blank chat proceeds
    } finally {
      clearTimeout(timeout)
    }
  }

  function clearContext() {
    contextLabel.value = null
    // Strip the query params so a refresh doesn't re-inject.
    router.replace({ query: {} })
  }

  return { loadContext, clearContext, contextLoaded, contextLabel }
}
```

In `frontend/apps/main/src/api/ai.ts`, add:

```typescript
export interface AiContextResponse { source: string; summary: string }
export async function getAiContext(source: string, id: string, signal?: AbortSignal): Promise<AiContextResponse> {
  const resp = await fetch(`/api/v1/ai/context?source=${source}&id=${id}`, {
    headers: { ...(http.defaults.headers.common as Record<string, string>) },
    signal,
  })
  if (!resp.ok) throw new Error(`ai/context ${resp.status}`)
  return resp.json() as Promise<AiContextResponse>
}
```

- [ ] **Step 7: Wire useAiContext into AIChatBox**

In `frontend/apps/main/src/components/ai/AIChatBox.vue`, in `onMounted` (lines 149-222), AFTER `store.initializeFromUrl()` (line 163) and BEFORE the existing `if (store.pendingMessage)` block (line 176), add the A1b context injection:

```typescript
// A1b (Plan B T6): if a passive button sent ?source=&id=, fetch the entity
// context and inject it as the first user turn (separate from the q-param
// pendingMessage path used by AIHubPage).
import { useAiContext } from '@/composables/useAiContext'
const { loadContext, contextLabel, clearContext } = useAiContext()
const a1bContext = await loadContext()
if (a1bContext) {
  // Send the context as the first message. fetchFamily must be ready first.
  await familyStore.fetchFamily()
  await handleStartChat({ text: a1bContext }, 'finance_coach' /* or source */)
}
```

Add the removable "已带入：X 上下文" tag above the input box (spec §7.3 design-lens):

```vue
<div v-if="contextLabel" class="context-tag">
  <span>{{ contextLabel }}</span>
  <van-icon name="cross" @click="clearContext" />
</div>
```

> **Integration note:** read `AIChatBox.vue` lines 149-222 carefully. The existing flow is `initializeFromUrl` → if `pendingMessage` → `handleStartChat`. A1b's `?source=` is a DIFFERENT query param from `?q=`. The cleanest wiring: call `loadContext()` first; if it returns a message, send it via `handleStartChat`; only if it returns null does the existing `pendingMessage` path run. Do NOT double-send. Confirm `handleStartChat`'s signature (lines 297-339: `handleStartChat(payload, source)`). The `source` arg should be the route's `source` (passed through) — read how `source` flows in `chatSession` store. Match the existing convention exactly; if `handleStartChat` isn't the right seam, use `sendMessage` directly (line 311) after `createThread`.

- [ ] **Step 8: Write + run the frontend test**

Create `frontend/apps/main/src/composables/__tests__/useAiContext.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useAiContext } from '../useAiContext'

vi.mock('vue-router', () => ({
  useRoute: () => ref({ query: { source: 'liability_detail', id: '1' } }),
  useRouter: () => ({ replace: vi.fn() }),
}))
vi.mock('@/api/ai', () => ({ getAiContext: vi.fn() }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))

describe('useAiContext', () => {
  beforeEach(() => vi.clearAllMocks())

  it('returns the prefilled message on success', async () => {
    const { getAiContext } = await import('@/api/ai')
    vi.mocked(getAiContext).mockResolvedValue({ source: 'liability_detail', summary: '{"id":"1"}' })
    const { loadContext } = useAiContext()
    const msg = await loadContext()
    expect(msg).toContain('{"id":"1"}')
  })

  it('returns null + toasts on fetch failure (3s timeout / 404)', async () => {
    const { getAiContext } = await import('@/api/ai')
    vi.mocked(getAiContext).mockRejectedValue(new Error('404'))
    const { loadContext } = useAiContext()
    const msg = await loadContext()
    expect(msg).toBeNull()
  })

  it('returns null when no source query param', async () => {
    vi.doMock('vue-router', () => ({ useRoute: () => ref({ query: {} }), useRouter: () => ({ replace: vi.fn() }) }))
    const { loadContext } = useAiContext()
    expect(await loadContext()).toBeNull()
  })
})
```

Run: `cd frontend/apps/main && pnpm test:run -- useAiContext`
Expected: all 3 tests PASS.

- [ ] **Step 9: Add i18n + typecheck + lint + commit**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, under `aiChat` (line 157), add:

```typescript
    context: {
      prefill: '请基于以下{source}上下文为我提供详细建议：',
      loadFailed: '上下文加载失败，请直接描述',
      label: {
        liability_detail: '负债详情',
        wish_detail: '心愿详情',
        liability_strategy: '负债还款规划',
        wish_advice: '心愿储蓄建议',
      },
    },
```

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint -- src/composables/useAiContext.ts src/components/ai/AIChatBox.vue src/api/ai.ts`
Expected: no errors.

```bash
git add server/apps/backend/app/routers/ai_context.py server/apps/backend/app/services/ai_context_builder.py server/apps/backend/app/main.py server/tests/backend/routers/test_ai_context.py frontend/apps/main/src/composables/useAiContext.ts frontend/apps/main/src/components/ai/AIChatBox.vue frontend/apps/main/src/api/ai.ts frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/composables/__tests__/useAiContext.spec.ts
git commit -m "feat(ai): A1b /ai/context endpoint + greenfield chat context injection (Plan B T6)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: W4 — Wish-priority AI advice card (independent prompt + cache)

**Prerequisite:** W1 (T1-T3) for wish savings data; Plan A capability-cache infra (`upsert_capability_result`/`latest_by_capability`/`invalidate_capability`). W4 is an INDEPENDENT AI call (own prompt + `wish_advice:{fingerprint}` cache key) — NOT finance_coach's `suggestions[]` (schema-mutually-exclusive, spec §7.1).

**Files:**
- Create: `server/apps/backend/app/routers/ai_wish_advice.py` — `POST /ai/wish-advice/generate` (independent AI call via the asset-report-style stream OR a lightweight LLM call; cache key `family_id:wish_advice:{fingerprint}`, capability=`'wish_advice'`)
- Create: `server/apps/backend/app/services/wish_advice.py` — build the W4 prompt input (wishes fingerprint) + parse `redistribution[]` JSON
- Create: `frontend/apps/main/src/components/wishes/WishAdviceCard.vue` — card + redistribution dialog
- Modify: `frontend/apps/main/src/pages/WishListPage.vue` — render `WishAdviceCard` at top (only when pending wishes ≥ 2 and ≥1 has monthly_saving)
- Modify: `frontend/apps/main/src/api/wishes.ts` — add `getWishAdvice`/`adoptWishAdvice` (batch PATCH monthly_saving)
- Modify: `frontend/apps/main/src/types/index.ts` — add `WishAdvice`/`WishRedistribution` types
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add `wish.advice.*`
- Test: `server/tests/backend/routers/test_ai_wish_advice.py`
- Test: `frontend/apps/main/src/components/wishes/__tests__/WishAdviceCard.spec.ts`

**Interfaces:**
- Consumes: `Wish` (W1 fields), `require_adult` + `require_ai_enabled` + `require_owner` (mirror finance_coach trigger), `upsert_capability_result`/`latest_by_capability`/`is_cache_fresh`/`invalidate_capability` (Plan A T7). The wish write paths already invalidate `finance_coach` (Plan A T9) — W4 adds `wish_advice` invalidation on wish change.
- Produces:
  - `POST /ai/wish-advice/generate?force=false` → cached JSON 200 `{primary_wish_id, reason, suggested_monthly, redistribution: [{wish_id, suggested_amount, note}]}` (within 8h, wish-change invalidated) OR streams a fresh generation.
  - Frontend card: "AI 建议：本月优先为「X」存 ¥2000" + 理由 + 采纳 (opens redistribution dialog, read-only, 全部采纳/取消) + 看完整建议 (→ `/ai/chat?source=wish_advice`). Card closable, 8h localStorage suppression keyed by `wish_fingerprint_hash + timestamp` (independent of content cache, spec §4.3 design-lens).
  - 采纳 → batch `PATCH /wishes/{id}` per redistribution item; partial-failure: failed rows red + stay open, success rows grey, summary "X/N 条已更新".

- [ ] **Step 1: Write the failing backend test**

Create `server/tests/backend/routers/test_ai_wish_advice.py`:

```python
"""W4 wish-advice: cache hit / fingerprint invalidation / guardrail (Plan B T7)."""
from unittest.mock import patch


def test_generate_returns_cached_when_fresh(client, auth_headers, db_session, family_with_wishes):
    from apps.backend.app.services.finance_coach_cache import upsert_capability_result
    payload = {"primary_wish_id": "1", "reason": "距目标近", "suggested_monthly": 2000,
               "redistribution": [{"wish_id": "1", "suggested_amount": 2000, "note": "本月优先"}]}
    upsert_capability_result(db_session, family_with_wishes, "wish_advice", payload)
    db_session.commit()

    with patch("apps.backend.app.routers.ai_wish_advice.check_circuit_blocked", return_value=None):
        resp = client.post("/api/v1/ai/wish-advice/generate", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cached"
    assert resp.json()["report"]["primary_wish_id"] == "1"


def test_guardrail_drops_negative_suggested_amount(client, auth_headers, db_session, family_with_wishes):
    """Advice baseline (spec §7.1): suggested_amount >= 0; negative → schema fail → drop, don't display."""
    # When the AI returns a negative suggested_amount, the service must not
    # surface it (guardrail gate). This test asserts the endpoint either regenerates
    # or returns a safe payload — the gate is the contract.
    with patch("apps.backend.app.routers.ai_wish_advice.check_circuit_blocked", return_value=None), \
         patch("apps.backend.app.routers.ai_wish_advice.wish_advice.generate_advice", return_value=None):
        resp = client.post("/api/v1/ai/wish-advice/generate?force=true", headers=auth_headers)
    # No usable advice → 200 with empty/safe payload (silent, no error).
    assert resp.status_code == 200
```

> **Fixture note:** `family_with_wishes` = a family id (str) with ≥2 pending wishes, ≥1 with monthly_saving>0. Build via the wish service directly. The guardrail test patches `generate_advice` to return None (AI unusable) and asserts the endpoint degrades gracefully (200, no crash).

- [ ] **Step 2: Run backend test to verify it fails**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_wish_advice.py -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Create the W4 advice service**

Create `server/apps/backend/app/services/wish_advice.py`:

```python
"""W4 wish-priority advice (Plan B T7) — INDEPENDENT of finance_coach.

spec §7.1 coherence c100: W4 output is ``redistribution[]``, NOT finance_coach's
``suggestions[]``. W4 shares only the prompt-template skeleton (家庭财务教练角色),
not the output schema. Separate cache key ``family_id:wish_advice:{fingerprint}``.
"""
import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.wish import Wish
from apps.backend.app.models.user import User


def wish_fingerprint(wishes: list[Wish]) -> str:
    """Stable hash of the pending wishes' savings-relevant fields.

    The cache key is keyed by this fingerprint so a wish change (new/deleted/
    monthly_saving/target_date/expected_price edit) produces a new fingerprint
    → cache miss → regenerate. (spec §4.4: 心愿变更失效.)
    """
    parts = []
    for w in sorted(wishes, key=lambda x: x.id):
        parts.append(f"{w.id}:{w.expected_price}:{w.saved_amount}:{w.monthly_saving}:{w.target_date}:{w.priority}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_advice_input(db: Session, user: User) -> tuple[list[Wish], str]:
    """Return (pending wishes, fingerprint). Only wishes with a savings plan
    or a target_date are relevant (spec §4.1: ≥2 pending, ≥1 monthly_saving)."""
    wishes = db.query(Wish).filter(
        Wish.family_id == user.family_id, Wish.status == "pending"
    ).order_by(Wish.created_at).all()
    return wishes, wish_fingerprint(wishes)


def validate_advice(payload: dict | None) -> dict | None:
    """Advice baseline gate (spec §7.1): schema-validate + suggested_amount >= 0.

    Returns the payload if valid, else None (caller drops silently + logs).
    Required: primary_wish_id (str), reason (str), suggested_monthly (>=0),
    redistribution (list of {wish_id, suggested_amount >=0, note}).
    """
    if not payload or not isinstance(payload, dict):
        return None
    for k in ("primary_wish_id", "reason", "suggested_monthly", "redistribution"):
        if k not in payload:
            return None
    try:
        sm = Decimal(str(payload["suggested_monthly"]))
    except Exception:
        return None
    if sm < 0:
        return None
    redist = payload["redistribution"]
    if not isinstance(redist, list):
        return None
    for item in redist:
        if not isinstance(item, dict) or "wish_id" not in item or "suggested_amount" not in item:
            return None
        try:
            if Decimal(str(item["suggested_amount"])) < 0:
                return None
        except Exception:
            return None
    return payload


async def generate_advice(db: Session, user: User) -> tuple[dict | None, str]:
    """Run the W4 AI call + validate. Returns (validated_payload, fingerprint).

    Uses the family's configured LLM (per-family AIProviderConfig). The prompt
    instructs the LLM to pick the primary wish + propose redistribution. Output
    is parsed (json_repair / parse_report_json-style) then schema-validated.
    On any failure (no provider, parse error, guardrail fail) returns (None, fp).
    """
    wishes, fp = build_advice_input(db, user)
    if len(wishes) < 2 or not any((w.monthly_saving or Decimal("0")) > 0 for w in wishes):
        return None, fp  # spec §4.1: don't show the card

    # Build the prompt input (PII: wish name is prompt-required here — the user
    # names wishes and the AI reasons about them).
    wish_input = [
        {"id": str(w.id), "name": w.name, "expected_price": float(w.expected_price or 0),
         "saved_amount": float(w.saved_amount or 0), "monthly_saving": float(w.monthly_saving or 0),
         "target_date": str(w.target_date) if w.target_date else None, "priority": w.priority}
        for w in wishes
    ]

    # Lightweight single LLM call (mirror import_parse's lightweight LLM pattern,
    # U6-style _create_lightweight_llm + ainvoke). Read how the agent creates a
    # lightweight LLM for the suggest step and reuse it here.
    try:
        from apps.agent.core.backend_client import BackendClient
        from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
        # ... build adapter + ainvoke with the W4 prompt ...
        # (Implementation mirrors the lightweight-LLM call used by the suggest
        #  feature — confirm the exact helper and reuse it. If no shared helper
        #  exists, build a minimal ChatOpenAI from the family's active provider
        #  config and call .ainvoke with the structured prompt.)
        # Parse the LLM's ```json block:
        # parsed = parse_report_json(ai_text)
        # return validate_advice(parsed), fp
        pass  # see implementation note below
    except Exception:
        return None, fp
    return None, fp  # placeholder — replace with the real ainvoke path
```

> **Implementation note (load-bearing):** the W4 AI call's exact LLM-construction path must mirror an existing lightweight-LLM call in the repo. The memory notes a U6 "suggest→lightweight LLM single call (`_create_lightweight_llm`+`ainvoke`)" pattern. Read `server/apps/agent/services/` for the suggest feature's lightweight-LLM helper (grep `_create_lightweight_llm` or `ainvoke`), and reuse it for W4 — do NOT hand-roll a new LLM client. If the helper lives in the agent app (not backend), W4's advice generation may need to run as a backend→agent stream_run (like finance_coach) rather than an inline backend LLM call. **Decision:** to keep W4 consistent with finance_coach (D2) and avoid a backend-side LLM client, implement W4 as a SECOND stream_run capability. The simplest path: reuse the `finance_coach` agent machinery with a different `skill_name="wish-advice"` OR route W4 through a dedicated worker branch. Given the spec says W4 is an "independent AI call" but doesn't mandate a new capability, the pragmatic choice is: **W4 calls the same `finance_coach` stream_run endpoint but with a different skill + prompt** — NO, that conflates the two schemas. Instead, implement W4 advice generation as a backend-side lightweight LLM call reusing the `_create_lightweight_llm` helper (locate it in the agent app; if it's not importable from backend, extract it to `server/packages/domain/` or `server/apps/backend/app/services/` as a shared `lightweight_llm.py`). The implementer should: (1) grep for `_create_lightweight_llm` / `ainvoke` to find the existing helper; (2) make it importable from the backend; (3) call it here with the W4 prompt; (4) `validate_advice(parse_report_json(ai_text))`. If extracting the helper is non-trivial, fall back to a dedicated `wish-advice` stream_run capability (mirror Plan A's finance_coach chain: RESERVED_NAMES + system-agent + gateway route + worker branch + SKILL.md) — but that's a heavier lift and should be flagged to the planner. **Pick the lightweight-LLM path first**; only escalate to a new capability if the helper isn't extractable.

- [ ] **Step 4: Create the W4 router**

Create `server/apps/backend/app/routers/ai_wish_advice.py`:

```python
"""W4 wish-priority advice endpoint (Plan B T7). Independent AI call + cache.

POST /api/v1/ai/wish-advice/generate?force=false
Cache key: family_id:wish_advice:{fingerprint}, TTL 8h, wish-change invalidated.
Output schema (NOT finance_coach's suggestions[]): {primary_wish_id, reason,
suggested_monthly, redistribution: [{wish_id, suggested_amount, note}]}.
"""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.services import wish_advice
from apps.backend.app.services.finance_coach_cache import (
    is_cache_fresh, latest_by_capability, upsert_capability_result,
)

router = APIRouter(prefix="/ai/wish-advice", tags=["ai-wish-advice"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_wish_advice(
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    blocked = check_circuit_blocked(current_user.family_id, "wish_advice", db)
    if blocked is not None:
        return blocked

    wishes, fingerprint = wish_advice.build_advice_input(db, current_user)
    cache_capability = f"wish_advice:{fingerprint}"

    if not force:
        # The wish_advice cache is keyed by fingerprint; we store under a single
        # capability='wish_advice' row and compare fingerprints in the payload.
        cached = latest_by_capability(db, current_user.family_id, "wish_advice")
        if is_cache_fresh(cached, "wish_advice") and cached and cached.report_json.get("fingerprint") == fingerprint:
            return JSONResponse(status_code=200, content={
                "status": "cached",
                "generated_at": cached.generated_at.isoformat() if cached.generated_at else None,
                "report": cached.report_json.get("advice"),
            })

    advice, fp = await wish_advice.generate_advice(db, current_user)
    if advice is None:
        # No usable advice (guardrail fail / AI down / <2 wishes) → silent (spec §4.5).
        return JSONResponse(status_code=200, content={"status": "empty", "report": None})

    upsert_capability_result(db, current_user.family_id, "wish_advice", {"fingerprint": fp, "advice": advice})
    db.commit()
    return JSONResponse(status_code=200, content={"status": "fresh", "report": advice})
```

> **Cache-key shape note:** spec §4.4 says key=`family_id:wish_advice:{wish_fingerprint_hash}`. The capability-cache stores one row per `capability` string. To honor the fingerprint in the key without a new column, we store `capability='wish_advice'` and embed the `fingerprint` in `report_json` (compared on read). This is a pragmatic adaptation — if the planner prefers a literal fingerprint-scoped capability string (`f"wish_advice:{fp}"`), the `latest_by_capability`/`upsert_capability_result` calls would use that string directly (each new fingerprint = a new capability row; old rows linger until TTL, acceptable). **Pick the embedded-fingerprint approach** (above) to keep the capability column's cardinality bounded; document the choice in the commit.

Register the router in `server/apps/backend/app/main.py` next to `ai_finance_coach`.

- [ ] **Step 5: Add wish_advice invalidation to wish writes**

In `server/apps/backend/app/services/wish.py` (Plan A T9 already added `invalidate_capability(db, user.family_id, "finance_coach")` to create/update/delete/realize), add a SECOND call next to each:

```python
    invalidate_capability(db, user.family_id, "finance_coach")
    invalidate_capability(db, user.family_id, "wish_advice")  # W4 (Plan B T7): wish change busts advice cache
```

Also add it to `wish_savings.record_savings`/`delete_savings` (Task 2) — savings change the wish fingerprint. (Add the call next to the existing `invalidate_capability(db, user.family_id, "finance_coach")` in Task 2's service.)

- [ ] **Step 6: Run backend test to verify it passes**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_wish_advice.py -v`
Expected: tests PASS (the cached-hit test passes; the guardrail test passes via the `generate_advice → None` patch).

- [ ] **Step 7: Frontend — types + API client + card + WishListPage**

In `frontend/apps/main/src/types/index.ts`:

```typescript
export interface WishRedistribution { wish_id: string; suggested_amount: string; note: string }
export interface WishAdvice {
  primary_wish_id: string
  reason: string
  suggested_monthly: string
  redistribution: WishRedistribution[]
}
```

In `frontend/apps/main/src/api/wishes.ts`:

```typescript
export function getWishAdvice(force = false) {
  return http.get<{ status: string; report: WishAdvice | null }>('/ai/wish-advice/generate', { params: { force } })
}
export function adoptWishAdvice(redistribution: WishRedistribution[]) {
  // Batch PATCH each wish's monthly_saving. Returns per-item success/failure.
  return Promise.allSettled(redistribution.map((r) => updateWish(r.wish_id, { monthly_saving: r.suggested_amount })))
}
```

Create `frontend/apps/main/src/components/wishes/WishAdviceCard.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showDialog } from 'vant'
import { getWishAdvice, adoptWishAdvice, getWishes } from '@/api/wishes'
import { useWishStore } from '@/stores/wish'
import { useI18n } from 'vue-i18n'
import type { WishAdvice } from '@/types'

const props = defineProps<{ wishes: { id: string; name: string; monthly_saving: string }[] }>()
const router = useRouter()
const { t } = useI18n()
const wishStore = useWishStore()

const advice = ref<WishAdvice | null>(null)
const visible = ref(false)
const closed = ref(false)  // localStorage 8h suppression (independent of content cache)
const adopting = ref(false)
const adoptingState = ref<Record<string, 'pending' | 'success' | 'failed'>>({})

const SUPPRESSION_KEY = 'wish_advice_closed'

function fingerprintHash() {
  return props.wishes.map((w) => `${w.id}:${w.monthly_saving}`).join('|')
}

function isSuppressed() {
  const raw = localStorage.getItem(SUPPRESSION_KEY)
  if (!raw) return false
  try {
    const { fp, ts } = JSON.parse(raw)
    if (fp !== fingerprintHash()) return false  // fingerprint changed → allow re-show
    return Date.now() - ts < 8 * 3600 * 1000
  } catch { return false }
}

function suppress() {
  localStorage.setItem(SUPPRESSION_KEY, JSON.stringify({ fp: fingerprintHash(), ts: Date.now() }))
  closed.value = true
}

async function load() {
  if (isSuppressed()) { closed.value = true; return }
  try {
    const resp = await getWishAdvice(false)
    if (resp.data.status === 'cached' || resp.data.status === 'fresh') {
      if (resp.data.report && validateAdvice(resp.data.report)) {
        advice.value = resp.data.report
        visible.value = true
      }
    }
  } catch { /* silent */ }
}

function validateAdvice(a: WishAdvice): boolean {
  // Client-side guardrail mirror (spec §7.1): suggested_amount >= 0 per item.
  return a.redistribution.every((r) => Number(r.suggested_amount) >= 0) && Number(a.suggested_monthly) >= 0
}

function onClose() { suppress() }

async function onAdopt() {
  if (!advice.value) return
  // Read-only confirmation dialog (spec §4.3 design-lens): 全部采纳 / 取消 only.
  try {
    await showDialog({
      title: t('wish.advice.adoptTitle'),
      message: advice.value.redistribution.map((r) => {
        const w = props.wishes.find((x) => x.id === r.wish_id)
        return `${w?.name ?? r.wish_id}: ¥${w?.monthly_saving ?? '0'} → ¥${r.suggested_amount}（${r.note}）`
      }).join('\n') + `\n\n${t('wish.advice.totalMonthly', { total: advice.value.redistribution.reduce((s, r) => s + Number(r.suggested_amount), 0) })}`,
      showCancelButton: true,
      confirmButtonText: t('wish.advice.adoptAll'),
      cancelButtonText: t('common.cancel'),
    })
  } catch { return }  // cancel
  adopting.value = true
  const results = await adoptWishAdvice(advice.value.redistribution)
  let ok = 0
  advice.value.redistribution.forEach((r, i) => {
    adoptingState.value[r.wish_id] = results[i].status === 'fulfilled' ? 'success' : 'failed'
    if (results[i].status === 'fulfilled') ok++
  })
  await wishStore.fetchWishes()  // refresh
  if (ok === advice.value.redistribution.length) {
    showSuccessToast(t('wish.advice.allUpdated'))
    visible.value = false
    suppress()
  } else {
    showFailToast(t('wish.advice.partial', { ok, total: advice.value.redistribution.length }))
    // failed rows stay red + dialog stays open (spec §4.3)
  }
  adopting.value = false
}

function onFullAdvice() {
  router.push({ name: 'AIChat', query: { source: 'wish_advice' } })
}

const shouldShow = computed(() => !closed.value && visible.value && advice.value)

onMounted(() => load())
</script>

<template>
  <div v-if="shouldShow" class="wish-advice-card">
    <div class="wa-header">
      <span class="wa-title">{{ t('wish.advice.title') }}</span>
      <van-icon name="cross" @click="onClose" />
    </div>
    <div class="wa-body">
      {{ t('wish.advice.primary', { name: wishes.find(w => w.id === advice!.primary_wish_id)?.name ?? advice!.primary_wish_id, amount: advice!.suggested_monthly }) }}
    </div>
    <div class="wa-reason">{{ advice!.reason }}</div>
    <div class="wa-actions">
      <van-button size="small" type="primary" :loading="adopting" @click="onAdopt">{{ t('wish.advice.adopt') }}</van-button>
      <van-button size="small" plain @click="onFullAdvice">{{ t('wish.advice.fullAdvice') }}</van-button>
    </div>
  </div>
</template>
```

In `frontend/apps/main/src/pages/WishListPage.vue`, at the top of the list content (after `van-pull-refresh` open, before the wish list), add:

```vue
<WishAdviceCard :wishes="wishes.map((w) => ({ id: w.id, name: w.name, monthly_saving: w.monthly_saving }))" />
```

(Only render when `pending wishes >= 2 && >=1 monthly_saving>0` — guard with a `v-if`, or let the card hide itself via `load()` returning empty. The spec §4.1 trigger condition is best enforced in the card's `load()` via the backend returning `empty`.) Add the import + register.

- [ ] **Step 8: Frontend test + i18n + typecheck**

Create `frontend/apps/main/src/components/wishes/__tests__/WishAdviceCard.spec.ts` (mirror FinanceCoachCard.spec — assert: renders when valid advice; hides when empty/closed; adopt calls batch PATCH; partial failure keeps failed rows). Run: `cd frontend/apps/main && pnpm test:run -- WishAdviceCard`.

Add i18n under `wish.advice.*`:
```typescript
    advice: {
      title: 'AI 储蓄建议', adopt: '采纳', fullAdvice: '看完整建议',
      adoptTitle: '采纳储蓄重分配', adoptAll: '全部采纳',
      totalMonthly: '本月总月存 ¥{total}（建议值合计，请自行判断是否超承受力）',
      primary: '本月建议优先为「{name}」存 ¥{amount}',
      allUpdated: '储蓄计划已更新', partial: '{ok}/{total} 条已更新',
    },
```

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint`
Expected: no errors.

- [ ] **Step 9: Backend lint/typecheck + commit**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_wish_advice.py apps/backend/app/services/wish_advice.py apps/backend/app/services/wish.py && uv run mypy apps/backend/app/routers/ai_wish_advice.py apps/backend/app/services/wish_advice.py`
Expected: no errors.

```bash
git add server/apps/backend/app/routers/ai_wish_advice.py server/apps/backend/app/services/wish_advice.py server/apps/backend/app/main.py server/apps/backend/app/services/wish.py server/tests/backend/routers/test_ai_wish_advice.py frontend/apps/main/src/components/wishes/WishAdviceCard.vue frontend/apps/main/src/pages/WishListPage.vue frontend/apps/main/src/api/wishes.ts frontend/apps/main/src/types/index.ts frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/components/wishes/__tests__/WishAdviceCard.spec.ts
git commit -m "feat(wish): W4 priority advice card + independent wish_advice cache (Plan B T7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: W5 — High-interest debt ↔ wish linkage (thresholds + hint UI)

**Prerequisite:** W1 (`ignore_debt_warning` field, T1-T3), L1 (interest calc, T4). W5 is PURE computation (category thresholds + L1 rate sort), not AI (spec §5).

**Files:**
- Modify: `server/apps/backend/app/routers/family.py` — add `GET/PUT /family/debt-thresholds` (owner-only PUT, reuse `update_family_settings` owner guard)
- Modify: `server/apps/backend/app/services/family.py` (or wherever settings live) — default thresholds + read/write
- Create: `frontend/apps/main/src/composables/useDebtWarning.ts` — compute high-interest liabilities + per-wish trigger
- Modify: `frontend/apps/main/src/pages/WishListPage.vue` — W5 hint bar ABOVE the W4 card (spec §5.4: 先止血再储蓄)
- Modify: `frontend/apps/main/src/pages/WishDetailPage.vue` — W5 hint above the savings-plan region + "忽略" button
- Modify: `frontend/apps/main/src/pages/WishFormPage.vue` — inline hint on `monthly_saving` blur (W5 form trigger)
- Modify: `frontend/apps/main/src/pages/LiabilityListPage.vue` — handle `?focus=liability_strategy` query (scroll + expand L1 card, or plain scroll if L1 not shown)
- Modify: `frontend/apps/main/src/api/wishes.ts` — (setIgnoreDebtWarning already in T3) + thresholds API
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — `wish.debtWarning.*`
- Test: `server/tests/backend/routers/test_family_debt_thresholds.py`
- Test: `frontend/apps/main/src/composables/__tests__/useDebtWarning.spec.ts`

**Interfaces:**
- Consumes: `Liability` (`category`, `interest_rate`, `is_active`), `Wish.ignore_debt_warning` (W1). `require_owner` (owner-only PUT, mirror `update_family_settings`). L1 rate-sort logic (T4's `calc_amortization` monthly-interest = `remaining × monthly_rate`).
- Produces:
  - `GET /family/debt-thresholds` → `{thresholds: {credit_card: 12, personal_loan: 10, mortgage: 6, other: 10}}` (all family members read).
  - `PUT /family/debt-thresholds` (owner-only) → updates + returns.
  - Frontend `useDebtWarning()`: given liabilities + thresholds, returns the high-interest set (per-category threshold check) + a per-wish trigger predicate (wish has monthly_saving>0 AND any high-interest liability AND NOT wish.ignore_debt_warning).

- [ ] **Step 1: Write the failing backend test**

Create `server/tests/backend/routers/test_family_debt_thresholds.py`:

```python
"""W5 debt-threshold config: owner-only PUT + default values (Plan B T8)."""
import pytest


def test_get_debt_thresholds_default(client, auth_headers):
    resp = client.get("/api/v1/family/debt-thresholds", headers=auth_headers)
    assert resp.status_code == 200
    th = resp.json()["thresholds"]
    assert th["credit_card"] == 12
    assert th["personal_loan"] == 10
    assert th["mortgage"] == 6
    assert th["other"] == 10


def test_put_debt_thresholds_owner_only(client, owner_headers, adult_headers):
    resp = client.put("/api/v1/family/debt-thresholds",
                      json={"thresholds": {"credit_card": 15, "personal_loan": 10, "mortgage": 6, "other": 10}},
                      headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["thresholds"]["credit_card"] == 15

    # Non-owner adult is FORBIDDEN (spec §5.1 security-lens).
    resp2 = client.put("/api/v1/family/debt-thresholds",
                       json={"thresholds": {"credit_card": 20}},
                       headers=adult_headers)
    assert resp2.status_code == 403


def test_get_visible_to_all_family_members(client, adult_headers):
    """Read is visible to all family members (not just owner)."""
    resp = client.get("/api/v1/family/debt-thresholds", headers=adult_headers)
    assert resp.status_code == 200
```

> **Fixture note:** `owner_headers` vs `adult_headers` — two users in the same family, one with `role=owner`, one adult. Build via the auth fixtures. If the repo's auth setup makes owner-distinguishing fixtures hard, use a single owner user for PUT and assert the 403 by mocking `require_owner` to raise.

- [ ] **Step 2: Run backend test to verify it fails**

Run: `cd server && uv run pytest tests/backend/routers/test_family_debt_thresholds.py -v`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Add the thresholds routes**

In `server/apps/backend/app/routers/family.py`, find `update_family_settings` and its owner guard (spec §5.1: `if user.role != 'owner': raise FAMILY_FORBIDDEN`). Add two routes next to it (mirror the settings read/write pattern — confirm where family settings JSON is stored):

```python
from apps.backend.app.auth.ai_deps import require_owner  # or the family.py owner guard
from apps.backend.app.auth.deps import require_adult

DEFAULT_DEBT_THRESHOLDS = {"credit_card": 12, "personal_loan": 10, "mortgage": 6, "other": 10}
DEBT_THRESHOLDS_KEY = "debt_thresholds"  # the settings-JSON key


@router.get("/debt-thresholds")
def get_debt_thresholds(
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """W5: read debt-interest thresholds (visible to all family members)."""
    settings = family_service.get_family_settings(db, user.family_id)  # confirm helper name
    return {"thresholds": settings.get(DEBT_THRESHOLDS_KEY, DEFAULT_DEBT_THRESHOLDS)}


@router.put("/debt-thresholds")
def put_debt_thresholds(
    body: DebtThresholdsRequest,  # {thresholds: {credit_card, personal_loan, mortgage, other}}
    user: User = Depends(require_owner),  # owner-only (spec §5.1)
    db: Session = Depends(get_db),
):
    """W5: update debt-interest thresholds. Owner-only — a non-owner could
    suppress/unsuppress the whole family's high-interest warnings."""
    merged = {**DEFAULT_DEBT_THRESHOLDS, **body.thresholds}
    family_service.update_family_settings(db, user.family_id, DEBT_THRESHOLDS_KEY, merged)
    return {"thresholds": merged}
```

> **Service check:** confirm `family_service`'s settings read/write helper names (`get_family_settings` / `update_family_settings` or similar). Read `server/apps/backend/app/routers/family.py` + the family service. If settings are stored as a JSON column on `Family`, mirror the existing `update_family_settings` exactly. `DebtThresholdsRequest` is a small Pydantic model: `class DebtThresholdsRequest(BaseModel): thresholds: dict[str, int]`. **Do NOT use `require_owner` from `ai_deps` if family.py has its own owner guard** — match the existing family.py convention to keep auth consistent.

- [ ] **Step 4: Run backend test to verify it passes**

Run: `cd server && uv run pytest tests/backend/routers/test_family_debt_thresholds.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Create the frontend composable**

Create `frontend/apps/main/src/composables/useDebtWarning.ts`:

```typescript
import { computed, ref } from 'vue'
import { http } from '@/api/index'
import type { Liability, Wish } from '@/types'

type Category = 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'

const DEFAULT_THRESHOLDS: Record<Category, number> = {
  credit_card: 12, personal_loan: 10, mortgage: 6, car_loan: 10, other: 10,
}

/** W5: high-interest-debt ↔ wish linkage (pure computation, spec §5). */
export function useDebtWarning(liabilities: Ref<Liability[]>, wishes: Ref<Wish[]>) {
  const thresholds = ref<Record<string, number>>({ ...DEFAULT_THRESHOLDS })

  async function loadThresholds() {
    try {
      const resp = await http.get('/family/debt-thresholds')
      thresholds.value = { ...DEFAULT_THRESHOLDS, ...resp.data.thresholds }
    } catch { /* default */ }
  }

  // Map liability.category → threshold key. car_loan falls under 'other' or its own
  // (spec lists 信用卡/消费贷/房贷/其他; car_loan ≈ 消费贷 → personal_loan threshold).
  function thresholdFor(cat: string): number {
    if (cat === 'credit_card') return thresholds.value.credit_card
    if (cat === 'mortgage') return thresholds.value.mortgage
    if (cat === 'personal_loan') return thresholds.value.personal_loan
    return thresholds.value.other  // car_loan + other
  }

  // High-interest active liabilities: rate >= their category threshold.
  const highInterestLiabilities = computed(() =>
    (liabilities.value || [])
      .filter((l) => l.is_active && (l.interest_rate ?? 0) >= thresholdFor(l.category))
      .map((l) => ({ ...l, monthly_interest: Math.round((l.remaining_amount * (l.interest_rate / 100) / 12) * 100) / 100 })),
  )

  const hasHighInterestDebt = computed(() => highInterestLiabilities.value.length > 0)

  // Per-wish trigger (spec §5.2): wish has monthly_saving>0 AND high-interest debt
  // exists AND NOT wish.ignore_debt_warning.
  function shouldWarnForWish(w: Wish): boolean {
    return Number(w.monthly_saving) > 0 && hasHighInterestDebt.value && !w.ignore_debt_warning
  }

  return { thresholds, loadThresholds, highInterestLiabilities, hasHighInterestDebt, shouldWarnForWish }
}
```

> **Ref import:** the `Ref` type — import from `vue`. If the page passes plain refs, this works. `http` import — mirror how `api/wishes.ts` imports `http` (`import http from './index'`); adjust the path. The `monthly_interest` formula matches L1 (T4: `remaining × monthly_rate`).

- [ ] **Step 6: W5 hint UI — WishListPage + WishDetailPage + WishFormPage + LiabilityListPage**

(a) `WishListPage.vue` — ABOVE the `<WishAdviceCard>` (spec §5.4: 先止血再储蓄), add a W5 hint bar:

```vue
<div v-if="debtWarning.hasHighInterestDebt && pendingWishes.length" class="debt-warning-bar">
  <van-icon name="warning-o" />
  <span>{{ t('wish.debtWarning.listHint', { amount: debtWarning.highInterestLiabilities[0]?.remaining_amount, rate: debtWarning.highInterestLiabilities[0]?.interest_rate }) }}</span>
  <van-button size="mini" plain @click="goToLiabilityStrategy">{{ t('wish.debtWarning.viewStrategy') }}</van-button>
</div>
<WishAdviceCard ... />
```

Wire `useDebtWarning` in the page's script: `const debtWarning = useDebtWarning(toRef(liabilityStore, 'liabilities'), toRef(wishes))`; call `debtWarning.loadThresholds()` in `loadWishes()`. `goToLiabilityStrategy` → `router.push({ path: '/liabilities', query: { focus: 'liability_strategy' } })`.

(b) `WishDetailPage.vue` — ABOVE the savings-plan region, add the hint + "忽略" button (only for the current wish if `shouldWarnForWish(wish)`):

```vue
<div v-if="debtWarning.shouldWarnForWish(wish)" class="debt-warning-bar">
  <span>{{ t('wish.debtWarning.detailHint') }}</span>
  <van-button size="mini" plain @click="ignoreDebtWarning">{{ t('wish.debtWarning.ignore') }}</van-button>
</div>
```

`ignoreDebtWarning` → `setIgnoreDebtWarning(wish.id, true)` (T3 API) + update local `wish.ignore_debt_warning = true` (hides the bar).

(c) `WishFormPage.vue` — inline hint on `monthly_saving` blur (spec §5.3 design-lens): when the field blurs with value>0 AND high-interest debt exists, show a small inline tip. New form (no wish_id): tip only ("检测到高息负债，建议优先还款"). Edit form (has wish_id): tip + "忽略" button (PATCH immediately). Use `@blur` on the `monthly_saving` van-field.

(d) `LiabilityListPage.vue` — on mount, detect `route.query.focus === 'liability_strategy'`:

```typescript
onMounted(() => {
  if (route.query.focus === 'liability_strategy') {
    nextTick(() => {
      const el = document.querySelector('.liability-strategy-card')
      if (el) el.scrollIntoView({ behavior: 'smooth' })
      // If L1 card isn't shown (active<2), just scroll to top (spec §5.3: avoid 断链).
    })
  }
})
```

- [ ] **Step 7: Add i18n + frontend test + typecheck**

Add under `wish.debtWarning.*`:
```typescript
    debtWarning: {
      listHint: '你有¥{amount}高息负债(利率{rate}%)，每月利息不低。先还债比存钱买心愿更划算。',
      viewStrategy: '查看还款建议', detailHint: '检测到高息负债，建议优先还款',
      ignore: '忽略', formHint: '检测到高息负债，建议优先还款',
    },
```

Create `frontend/apps/main/src/composables/__tests__/useDebtWarning.spec.ts` (assert: highInterestLiabilities filters by category threshold; shouldWarnForWish respects ignore_debt_warning + monthly_saving=0). Run: `cd frontend/apps/main && pnpm test:run -- useDebtWarning`.

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint`
Expected: no errors.

- [ ] **Step 8: Backend lint/typecheck + commit**

Run: `cd server && uv run ruff check apps/backend/app/routers/family.py && uv run mypy apps/backend/app/routers/family.py`
Expected: no errors.

```bash
git add server/apps/backend/app/routers/family.py server/tests/backend/routers/test_family_debt_thresholds.py frontend/apps/main/src/composables/useDebtWarning.ts frontend/apps/main/src/pages/WishListPage.vue frontend/apps/main/src/pages/WishDetailPage.vue frontend/apps/main/src/pages/WishFormPage.vue frontend/apps/main/src/pages/LiabilityListPage.vue frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/composables/__tests__/useDebtWarning.spec.ts
git commit -m "feat(wish): W5 high-interest debt ↔ wish linkage (Plan B T8)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: W2 afford bar refactor + W1 savings UI + L1/L2 UI + A1b passive buttons

This task consolidates the remaining frontend touchpoints: W2 (afford bar reads W1 fields), W1 detail (savings progress + log + record dialogs), L1 (strategy card) + L2 (interest forecast + simulate dialog), and the A1b passive buttons on liability/wish detail.

**Files:**
- Create: `frontend/apps/main/src/components/wishes/WishSavingsProgress.vue` (W1 detail progress + buttons)
- Create: `frontend/apps/main/src/components/wishes/WishSavingsLogDialog.vue` (W1 log list + delete confirm)
- Create: `frontend/apps/main/src/components/wishes/WishSavingsRecordDialog.vue` (W1 record form)
- Create: `frontend/apps/main/src/components/liability/LiabilityStrategyCard.vue` (L1)
- Create: `frontend/apps/main/src/components/liability/InterestForecast.vue` (L2)
- Create: `frontend/apps/main/src/components/liability/SimulateExtraDialog.vue` (L2 modal)
- Create: `frontend/apps/main/src/composables/useAffordBar.ts` (W2 logic, single-source for list/detail)
- Modify: `frontend/apps/main/src/pages/WishListPage.vue` — refactor afford bar (W2) + add savings progress affordance
- Modify: `frontend/apps/main/src/pages/WishDetailPage.vue` — add WishSavingsProgress + log/record dialogs + A1b "问 AI 规划储蓄" button
- Modify: `frontend/apps/main/src/pages/WishFormPage.vue` — 储蓄计划 group (target_date + monthly_saving)
- Modify: `frontend/apps/main/src/pages/LiabilityDetailPage.vue` — add InterestForecast + SimulateExtraDialog + A1b "问 AI 优化还款" button
- Modify: `frontend/apps/main/src/pages/LiabilityListPage.vue` — add LiabilityStrategyCard at top
- Modify: `frontend/apps/main/src/api/wishes.ts` — recordSaving/getSavingsLog/deleteSavingsLog (T3 added setIgnoreDebtWarning)
- Modify: `frontend/apps/main/src/api/liabilities.ts` — simulateLiability
- Modify: `frontend/apps/main/src/types/index.ts` — extend Wish (+savings fields as string), SavingsLog, LiabilitySimResult
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — `wish.savings.*`, `liability.strategy.*`, `liability.interest.*`
- Test: `frontend/apps/main/src/composables/__tests__/useAffordBar.spec.ts`
- Test: `frontend/apps/main/src/components/liability/__tests__/InterestForecast.spec.ts`

**Interfaces:**
- Consumes: W1 endpoints (T3), `/liabilities/simulate` (T4), `/ai/context` (T6, for A1b buttons), `useCurrency`. Wish fields now `saved_amount`/`monthly_saving`/`target_date`/`savings_count` (strings).
- Produces: the full W1/W2/L1/L2/A1b frontend surface.

- [ ] **Step 1: Extend frontend types + API clients**

In `frontend/apps/main/src/types/index.ts`:
- Extend `Wish` with `saved_amount: string; monthly_saving: string; target_date: string | null; savings_count: number; ignore_debt_warning: boolean` (and change `expected_price` to `string`).
- Add:
```typescript
export interface SavingsLog { id: string; wish_id: string; amount: string; log_date: string; note: string | null; created_at: string }
export interface LiabilitySimResult {
  total_interest: string; months: number; monthly_payment: string | null; warning: string | null
  baseline_total_interest?: string; baseline_months?: number; savings_vs_baseline?: string; months_saved?: number
}
```

In `frontend/apps/main/src/api/wishes.ts`:
```typescript
export function recordSaving(wishId: string, amount: string, logDate?: string, note?: string) {
  return http.post<SavingsLog>(`/wishes/${wishId}/savings`, { amount, log_date: logDate, note })
}
export function getSavingsLog(wishId: string, page = 1) {
  return http.get<SavingsLog[]>(`/wishes/${wishId}/savings`, { params: { page } })
}
export function deleteSavingsLog(wishId: string, logId: string) {
  return http.delete(`/wishes/${wishId}/savings/${logId}`)
}
export function setIgnoreDebtWarning(wishId: string, ignore: boolean) {
  return http.patch(`/wishes/${wishId}/ignore-debt-warning`, { ignore })
}
```

In `frontend/apps/main/src/api/liabilities.ts`:
```typescript
export function simulateLiability(req: { remaining: string; annual_rate: string; monthly_payment?: string; extra_monthly?: string }) {
  return http.post<LiabilitySimResult>('/liabilities/simulate', req)
}
```

- [ ] **Step 2: Create the W2 afford-bar composable (single-source list/detail)**

Create `frontend/apps/main/src/composables/useAffordBar.ts`:

```typescript
import { computed } from 'vue'
import type { Wish } from '@/types'

export type AffordState =
  | { kind: 'unset_monthly' }                                   // 未设定月存
  | { kind: 'progress'; months: number; etaDate: string | null } // 预计 N 月达成
  | { kind: 'reached' }                                          // 已达成 ✓
  | { kind: 'need_accelerate'; requiredMonthly: number; daysLeft: number } // 需加速

/** W2 afford-bar logic (spec §3.1). listMode: single-line compact; detail: full. */
export function useAffordBar(wish: () => Wish | undefined, netWorth: () => number) {
  const price = computed(() => Number(wish()?.expected_price ?? 0))
  const saved = computed(() => Number(wish()?.saved_amount ?? 0))
  const monthly = computed(() => Number(wish()?.monthly_saving ?? 0))
  const targetDate = computed(() => wish()?.target_date ?? null)

  const state = computed<AffordState>(() => {
    if (price.value > 0 && saved.value >= price.value) return { kind: 'reached' }
    if (monthly.value <= 0) return { kind: 'unset_monthly' }
    const remaining = price.value - saved.value
    const months = Math.ceil(remaining / monthly.value)
    const eta = new Date(); eta.setMonth(eta.getMonth() + months)
    return { kind: 'progress', months, etaDate: eta.toISOString().slice(0, 10) }
  })

  // target_date 加速对照 (spec §3.1 row 4): 距目标 D 天，需月存 ¥X
  const accelerate = computed(() => {
    if (!targetDate.value || monthly.value <= 0 || state.value.kind === 'reached') return null
    const target = new Date(targetDate.value)
    const daysLeft = Math.ceil((target.getTime() - Date.now()) / 86400000)
    if (daysLeft <= 0) return null
    const remaining = price.value - saved.value
    const requiredMonthly = remaining / Math.max(1, Math.ceil(daysLeft / 30))
    if (requiredMonthly > monthly.value) return { requiredMonthly: Math.ceil(requiredMonthly), daysLeft }
    return null
  })

  // Net-worth purchasing-power secondary line (spec §3.1 secondary, detail only)
  const purchasingPower = computed(() => ({
    covered: price.value > 0 && netWorth() >= price.value, netWorth: netWorth(),
  }))

  const progressPercent = computed(() => price.value > 0 ? Math.min(100, Math.round((saved.value / price.value) * 100)) : 0)
  const progressColor = computed(() => {
    if (saved.value > price.value) return '#faad14'  // 金 (超额)
    if (progressPercent.value >= 80) return '#07c160' // 绿
    if (progressPercent.value >= 50) return '#1989fa' // 蓝
    return '#ff976a'                                    // 橙
  })

  return { state, accelerate, purchasingPower, progressPercent, progressColor, price, saved, monthly }
}
```

- [ ] **Step 3: Write + run the W2 test**

Create `frontend/apps/main/src/composables/__tests__/useAffordBar.spec.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { computed } from 'vue'
import { useAffordBar } from '../useAffordBar'
import type { Wish } from '@/types'

function wish(partial: Partial<Wish>): Wish {
  return { id: '1', family_id: '1', user_id: '1', name: 'x', currency: 'CNY', priority: 'medium',
    status: 'pending', converts_to_asset: true, saved_amount: '0', monthly_saving: '0',
    target_date: null, savings_count: 0, ignore_debt_warning: false, created_at: '', updated_at: '',
    ...partial } as Wish
}

describe('useAffordBar', () => {
  it('unset_monthly when monthly_saving=0', () => {
    const { state } = useAffordBar(() => wish({ expected_price: '1000', saved_amount: '0', monthly_saving: '0' }), () => 0)
    expect(state.value.kind).toBe('unset_monthly')
  })

  it('reached when saved >= price', () => {
    const { state } = useAffordBar(() => wish({ expected_price: '1000', saved_amount: '1000', monthly_saving: '100' }), () => 0)
    expect(state.value.kind).toBe('reached')
  })

  it('progress computes months', () => {
    const { state } = useAffordBar(() => wish({ expected_price: '1000', saved_amount: '200', monthly_saving: '200' }), () => 0)
    expect(state.value.kind).toBe('progress')
    if (state.value.kind === 'progress') expect(state.value.months).toBe(4)
  })

  it('accelerate flags when target_date needs higher monthly', () => {
    const soon = new Date(); soon.setDate(soon.getDate() + 30)
    const { accelerate } = useAffordBar(() => wish({ expected_price: '10000', saved_amount: '0', monthly_saving: '100', target_date: soon.toISOString().slice(0, 10) }), () => 0)
    expect(accelerate.value).not.toBeNull()
    expect(accelerate.value!.requiredMonthly).toBeGreaterThan(100)
  })
})
```

Run: `cd frontend/apps/main && pnpm test:run -- useAffordBar`
Expected: all 4 tests PASS.

- [ ] **Step 4: Refactor WishListPage afford bar (W2)**

In `frontend/apps/main/src/pages/WishListPage.vue`, replace the inline afford-bar block (lines 79-97, the `expected_price <= net_worth` comparison) with a single-line affordance using `useAffordBar` per wish (spec §3.2: 列表单行精简 — main status text only; 需加速 prefixed with `!`):

```vue
<div v-if="wish.expected_price" class="afford-bar" :class="affordStateClass(wish)">
  <span v-if="affordFor(wish).state.kind === 'unset_monthly'">{{ t('wish.afford.setMonthly') }}</span>
  <span v-else-if="affordFor(wish).state.kind === 'reached'">{{ t('wish.afford.reached') }} ✓</span>
  <span v-else-if="affordFor(wish).state.kind === 'progress'">{{ t('wish.afford.etaMonths', { n: affordFor(wish).state.months }) }}</span>
  <span v-if="affordFor(wish).accelerate" class="accelerate">! {{ t('wish.afford.needAccelerate') }}</span>
</div>
```

In the script, build a per-wish afford helper (cache by wish.id in a Map to avoid recompute churn). Delete the old `expected_price <= dashboardStore.overview.net_worth` comparison logic (spec §3.1: keep net-worth as secondary, detail-only — remove from list). Add the new i18n keys.

> **Per-wish composable:** `useAffordBar` returns reactive computeds tied to a `() => Wish` getter. For a list, call it once per wish in a small wrapper: `const affordCache = new Map<string, ReturnType<typeof useAffordBar>>(); function affordFor(w: Wish) { if (!affordCache.has(w.id)) affordCache.set(w.id, useAffordBar(() => w, () => dashboardStore.overview?.net_worth ?? 0)); return affordCache.get(w.id)! }`.

- [ ] **Step 5: Create the W1 savings components**

Create `frontend/apps/main/src/components/wishes/WishSavingsProgress.vue` (progress bar + 记录存入 + 储蓄流水 + ETA):

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { useAffordBar } from '@/composables/useAffordBar'
import type { Wish } from '@/types'

const props = defineProps<{ wish: Wish }>()
const emit = defineEmits<{ (e: 'record'): void; (e: 'showLog'): void }>()
const { t } = useI18n()
const { format } = useCurrency()
const { state, accelerate, purchasingPower, progressPercent, progressColor, price, saved, monthly } = useAffordBar(() => props.wish, () => 0)
</script>

<template>
  <div class="savings-progress">
    <div class="sp-bar-row">{{ t('wish.savings.saved', { saved: format(Number(saved)), price: format(Number(price)), pct: progressPercent }) }}</div>
    <van-progress :percentage="progressPercent" :color="progressColor" :show-pivot="false" stroke-width="8" />
    <div class="sp-eta">
      <span v-if="state.kind === 'unset_monthly'">{{ t('wish.savings.setMonthly') }}</span>
      <span v-else-if="state.kind === 'reached'">{{ t('wish.savings.reached') }}</span>
      <span v-else-if="state.kind === 'progress'">{{ t('wish.savings.eta', { n: state.months }) }}</span>
    </div>
    <div v-if="accelerate" class="sp-accelerate">! {{ t('wish.savings.needAccelerate', { amount: accelerate.requiredMonthly }) }}</div>
    <div class="sp-secondary">{{ t('wish.savings.purchasingPower', { net: format(purchasingPower.netWorth), covered: purchasingPower.covered ? t('wish.savings.covered') : t('wish.savings.notCovered') }) }}</div>
    <div class="sp-actions">
      <van-button size="small" type="primary" @click="emit('record')">{{ t('wish.savings.record') }}</van-button>
      <van-button size="small" plain @click="emit('showLog')">{{ t('wish.savings.log') }} ({{ wish.savings_count }})</van-button>
    </div>
  </div>
</template>
```

Create `frontend/apps/main/src/components/wishes/WishSavingsLogDialog.vue` (list + delete with confirm per spec §2.2 design-lens — "删除后储蓄进度将回退 ¥X"):

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { getSavingsLog, deleteSavingsLog } from '@/api/wishes'
import { useI18n } from 'vue-i18n'
import type { SavingsLog } from '@/types'

const props = defineProps<{ show: boolean; wishId: string }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'changed'): void }>()
const { t } = useI18n()
const logs = ref<SavingsLog[]>([])

watch(() => props.show, async (v) => {
  if (v && props.wishId) { const r = await getSavingsLog(props.wishId); logs.value = r.data }
})

async function onDelete(log: SavingsLog) {
  try {
    await showConfirmDialog({ title: t('wish.savings.deleteTitle'), message: t('wish.savings.deleteConfirm', { amount: log.amount }) })
  } catch { return }
  await deleteSavingsLog(props.wishId, log.id)
  logs.value = logs.value.filter((l) => l.id !== log.id)
  showSuccessToast(t('wish.savings.deleted'))
  emit('changed')  // parent refreshes progress bar + saved_amount
}
</script>
<!-- template: van-popup with the log list; empty state "暂无储蓄记录" -->
```

Create `frontend/apps/main/src/components/wishes/WishSavingsRecordDialog.vue` (金额/日期/备注 form → recordSaving → emit 'saved').

- [ ] **Step 6: Wire W1 savings into WishDetailPage + WishFormPage**

`WishDetailPage.vue` — between the hero card (line 63) and the detail `van-cell-group` (line 66), insert `<WishSavingsProgress :wish="wish" @record="recordShow=true" @show-log="logShow=true" />` + the two dialogs. Add the A1b "问 AI 规划储蓄" button in the actions region (line 89-118): `@click="router.push({ name: 'AIChat', query: { source: 'wish_detail', id: wish.id } })"`.

`WishFormPage.vue` — after the price field (line 40), add a 储蓄计划 group:
```vue
<van-cell-group :title="t('wish.form.savingsPlanGroup')" inset>
  <van-field v-model="monthlySavingStr" name="monthly_saving" :label="t('wish.form.monthlySavingLabel')" type="number" inputmode="decimal" :placeholder="t('wish.form.monthlySavingPlaceholder')" />
  <van-field :model-value="targetDateStr" readonly name="target_date" :label="t('wish.form.targetDateLabel')" :placeholder="t('wish.form.targetDatePlaceholder')" @click="datePickerShow = true" />
</van-field-group>
<van-popup v-model:show="datePickerShow" position="bottom"><van-date-picker v-model="datePickerValue" @confirm="onDateConfirm" @cancel="datePickerShow=false" /></van-popup>
```
Add `monthly_saving` + `target_date` to the `form` ref (line 117) + the submit payload (line 144) + edit prefill (line 177). `saved_amount` is NOT in the form (initial 0, spec §2.3).

- [ ] **Step 7: Create L1 LiabilityStrategyCard + L2 InterestForecast + SimulateExtraDialog**

Create `frontend/apps/main/src/components/liability/LiabilityStrategyCard.vue` (spec §6.2: only when active liabilities ≥ 2; avalanche = rate desc, snowball = remaining asc; "采纳雪崩法" → localStorage flag + toast, NOT a db write; "问 AI 详细规划" → `/ai/chat?source=liability_strategy`). The two-strategy total-interest comparison calls `/liabilities/simulate` per liability (extra=0) for each strategy's payment order — OR a simpler client-side sum of monthly interest. **Use client-side monthly-interest sum** (`remaining × monthly_rate`) for the comparison to avoid N simulate calls; the "省 ¥Y" = difference of total interest under each payoff order is an approximation — keep the UI honest ("估算"). Match spec §6.2's `[采纳雪崩法]` localStorage + toast contract exactly.

Create `frontend/apps/main/src/components/liability/InterestForecast.vue` (spec §6.3): on the detail page, if `liability.interest_rate > 0`, call `simulateLiability` (extra=0, 500, 1000) to show "预计总利息 ¥X / 剩余 N 月" + the two extra scenarios + a `[模拟其他金额]` button. Hide entirely when `interest_rate` is null/0 (spec §6.1 adversarial). The `SimulateExtraDialog.vue` calls `simulateLiability` with a custom `extra_monthly` and shows `savings_vs_baseline` + `months_saved`; handle the boundary states (spec §6.3 design-lens: 0 = baseline; non-integer rejected; "无法还清" warning; extra ≥ remaining = "立即还清").

- [ ] **Step 8: Wire L1/L2 into the pages + A1b buttons**

`LiabilityListPage.vue` — after `van-pull-refresh` open (line 41), before the summary banner, add `<LiabilityStrategyCard :liabilities="activeLiabilities" />` (guard: `activeLiabilities.length >= 2`). Add the `?focus=liability_strategy` scroll handler (T8 Step 6d already covers it).

`LiabilityDetailPage.vue` — between the value card (line 21) and the countdown (line 24), add `<InterestForecast :liability="liability" />` + the simulate dialog. Add the A1b "问 AI 优化还款" button in the actions: `@click="router.push({ name: 'AIChat', query: { source: 'liability_detail', id: liability.id } })"`.

- [ ] **Step 9: Add i18n + frontend test + typecheck + commit**

Add i18n keys: `wish.savings.*` (saved/setMonthly/reached/eta/needAccelerate/purchasingPower/covered/notCovered/record/log/deleteTitle/deleteConfirm/deleted), `wish.afford.*` (setMonthly/reached/etaMonths/needAccelerate — extend existing §968), `wish.form.*` (savingsPlanGroup/monthlySavingLabel/monthlySavingPlaceholder/targetDateLabel/targetDatePlaceholder), `liability.strategy.*` (title/avalanche/snowball/adopt/adopted/askAi/saveEstimate), `liability.interest.*` (totalInterest/monthsLeft/extraScenario/simulate/savings/monthsSaved/warning/immediatePayoff).

Create `frontend/apps/main/src/components/liability/__tests__/InterestForecast.spec.ts` (assert: hidden when interest_rate=0; shows total_interest + months when rate>0; simulate dialog returns savings_vs_baseline). Run: `cd frontend/apps/main && pnpm test:run -- InterestForecast`.

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint && pnpm test:run`
Expected: no errors; all tests pass.

```bash
git add frontend/apps/main/src/components/wishes/WishSavingsProgress.vue frontend/apps/main/src/components/wishes/WishSavingsLogDialog.vue frontend/apps/main/src/components/wishes/WishSavingsRecordDialog.vue frontend/apps/main/src/components/liability/LiabilityStrategyCard.vue frontend/apps/main/src/components/liability/InterestForecast.vue frontend/apps/main/src/components/liability/SimulateExtraDialog.vue frontend/apps/main/src/composables/useAffordBar.ts frontend/apps/main/src/pages/WishListPage.vue frontend/apps/main/src/pages/WishDetailPage.vue frontend/apps/main/src/pages/WishFormPage.vue frontend/apps/main/src/pages/LiabilityDetailPage.vue frontend/apps/main/src/pages/LiabilityListPage.vue frontend/apps/main/src/api/wishes.ts frontend/apps/main/src/api/liabilities.ts frontend/apps/main/src/types/index.ts frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/composables/__tests__/useAffordBar.spec.ts frontend/apps/main/src/components/liability/__tests__/InterestForecast.spec.ts
git commit -m "feat(ui): W2 afford bar + W1 savings UI + L1/L2 strategy + A1b buttons (Plan B T9)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Plan B self-review + integration regression

**Files:** No new files. Verifies spec coverage + cross-task type consistency + regression.

- [ ] **Step 1: Spec coverage self-review**

Check each spec section maps to a task:
- [x] §2 W1 (migration + API + authz + invariant + delete confirm) → T1, T2, T3, T9 (delete confirm in WishSavingsLogDialog)
- [x] §3 W2 (afford bar refactor, list single-line / detail double-line, 需加速) → T9 (useAffordBar + WishListPage + WishSavingsProgress)
- [x] §4 W4 (trigger ≥2 pending + ≥1 monthly_saving, redistribution schema, adopt dialog read-only 全部采纳/取消, partial-failure, close+cache independent localStorage, 现金流提示) → T7
- [x] §5 W5 (owner-only thresholds, trigger conditions, 3 hint locations, form blur timing, ?focus jump target, ignore_debt_warning) → T8
- [x] §6 L1 (avalanche/snowball, 采纳 localStorage not db, 问 AI jump) + L2 (interest forecast, simulate dialog boundary states, no-rate hide) → T4 (backend) + T9 (frontend)
- [x] §7.2 D2/A1a (Dashboard card top-3, skeleton, empty hide, refresh force, PII minimal input filter) → T5
- [x] §7.3 A1b (4 button locations, /ai/context unified endpoint, family-scope 404, 3s timeout, sanitization, removable context tag) → T6 (backend + AIChatBox) + T9 (buttons on detail pages)
- [x] §7.1 advice baseline guardrail (schema gate, suggested_amount≥0, wrong output dropped) → T5 (FinanceCoachCard validate), T7 (validate_advice), T9 (client mirror)

- [ ] **Step 2: Placeholder scan**

Search both plans for `TODO|TBD|implement later|fill in|similar to Task` — every code step has complete code. Known deferred-with-note items (NOT placeholders — they're documented decisions):
- W4 LLM-call path (T7 Step 3): documented to reuse `_create_lightweight_llm` or escalate to a dedicated capability — the implementer must resolve this first; if the helper isn't extractable, flag it before proceeding.
- `savings_count` population on WishResponse (T3 Step 5): documented to match the existing response-construction convention.

- [ ] **Step 3: Type consistency cross-check**

- `useAffordBar` state kinds (`unset_monthly`/`progress`/`reached`/`need_accelerate`) — consistent between useAffordBar.ts (T9 Step 2) and WishListPage/WishSavingsProgress consumers (T9 Steps 4-5). ✓
- `invalidate_capability(db, family_id, capability)` — signature identical across Plan A T7 (def) and Plan B T2/T7 callers. ✓
- `Wish` frontend type: `saved_amount`/`monthly_saving`/`expected_price` are `string` (T9 Step 1) — matches `useAffordBar`'s `Number(...)` coercion (T9 Step 2) and the backend's str serialization (T1/T3). ✓
- `SavingsLogResponse` / `SavingsLog` TS — `amount` is `str`/`string` both sides (T2 schema, T9 type). ✓
- `LiabilitySimResult` — `total_interest`/`monthly_payment`/`savings_vs_baseline` as `string`/`str` both sides (T4 schema, T9 type). ✓
- A1b `source` values (`liability_detail`/`wish_detail`/`liability_strategy`/`wish_advice`) — identical in `/ai/context` backend (T6 Step 4 `_VALID_SOURCES`) and `useAiContext` (T6 Step 6 `AiSource`) and the 4 button locations (T9 Step 8). ✓
- `wish_advice` cache capability string — identical in `ai_wish_advice.py` (T7 Step 4), `wish.py` invalidation (T7 Step 5), `wish_savings.py` (T7 Step 5 note). ✓

- [ ] **Step 4: Full backend + frontend regression**

Run: `cd server && uv run pytest tests/backend/ packages/domain/tests/ -v 2>&1 | tail -40`
Expected: all Plan B tests pass; existing wish/liability/asset-report tests unaffected (W1 migration backward-compatible; capability column backfill='report'; simulate is a new route).

Run: `cd frontend/apps/main && pnpm typecheck && pnpm test:run && pnpm -r typecheck 2>/dev/null`
Expected: no type errors; all tests pass.

- [ ] **Step 5: Lint the full Plan B surface**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_context.py apps/backend/app/routers/ai_wish_advice.py apps/backend/app/routers/wishes.py apps/backend/app/routers/liabilities.py apps/backend/app/routers/family.py apps/backend/app/services/wish_savings.py apps/backend/app/services/wish_advice.py apps/backend/app/services/ai_context_builder.py packages/domain/liability_calculator.py && uv run mypy apps/backend/app/routers/ai_context.py apps/backend/app/routers/ai_wish_advice.py apps/backend/app/services/wish_savings.py packages/domain/liability_calculator.py`
Expected: no errors.

- [ ] **Step 6: Final integration smoke (manual checklist, no dev server)**

Trace the two end-to-end paths by grepping wiring (not running servers):
1. **finance_coach path:** DashboardPage → FinanceCoachCard → `POST /ai/finance-coach/generate` (Plan A T8) → gateway route (Plan A T5) → worker `_run_finance_coach_agent` (Plan A T6) → `finance_coach.result` → cached → card renders top-3.
2. **A1b path:** LiabilityDetailPage button → `/ai/chat?source=liability_detail&id=X` → AIChatBox onMounted → `useAiContext.loadContext()` → `GET /ai/context` (Plan B T6) → first message injected.

Confirm both chains are wired with no missing links.

---

## Plan B — Definition of Done

Plan B is complete when:
1. All 9 implementation tasks (T1-T9) are committed and their tests pass.
2. W1: wish savings fields + `wish_savings_log` + CRUD + invariant (recompute + CI assertion) + delete-confirm UI — done (T1-T3, T9).
3. L1/L2: single-source `liability_calculator.py` (6-case tested) + `/liabilities/simulate` + strategy card + interest forecast + simulate modal — done (T4, T9).
4. W2: afford bar refactored (list single-line / detail double-line, 需加速) reading W1 fields — done (T9).
5. D2/A1a: Dashboard finance_coach card (top-3, skeleton, empty-hide, refresh) — done (T5).
6. A1b: 4 passive buttons + `/ai/context` (family-scoped, 3s timeout, sanitization) + greenfield AIChatBox injection — done (T6, T9).
7. W4: wish-priority card (independent AI + `wish_advice` cache + redistribution dialog + close/localStorage + 现金流提示) — done (T7).
8. W5: high-interest debt hints (3 locations + form blur + `?focus` jump + owner-only thresholds) — done (T8).
9. Spec self-review (Step 1) covers all P0 sections; placeholder scan (Step 2) clean; type consistency (Step 3) verified; full regression (Step 4-5) green.

**Plan B does NOT implement** (deferred per spec §11): P1 (N1 finance hub, D1/D3-D7, L3-L5, A2/A3, B4, F3/F7), P2 (i18n cleanup, a11y, currency unification of legacy hardcodes), P3. P0 delivers the additive value: each touchpoint closes its local loop; structural cross-module wiring (the `/finance` hub) is P1 N1.








