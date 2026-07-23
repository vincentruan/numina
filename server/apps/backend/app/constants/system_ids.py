"""System agent and skill IDs — single source of truth for all runtime references.

These IDs are assigned at bootstrap time and must stay stable across deployments.
Alembic migration files use raw literals (historical snapshots) and are intentionally
excluded from this module — do not import from here in migration scripts.
"""

# System agent IDs (family_id=0, agent_type="system")
NUMINA_AGENT_ID: int = 100000000000005
ASSET_REPORT_AGENT_ID: int = 100000000000006
IMPORT_PARSE_AGENT_ID: int = 100000000000007
# Plan A: finance-coach system agent (家庭财务处方建议). Stateless stream_run
# agent — each run builds a fresh family finance snapshot; DeerMem would
# pollute advice with stale snapshots. soul_md is a minimal persona (the real
# advice contract lives in skills/builtin/public/finance-coach/SKILL.md).
FINANCE_COACH_AGENT_ID: int = 100000000000008
# Plan B T7: wish-advice system agent (W4 心愿优先储蓄建议). Stateless stream_run
# agent — each run builds a fresh wishes snapshot; DeerMem would pollute advice
# with stale wish state. soul_md is a minimal persona (the real advice contract
# lives in skills/builtin/public/wish-advice/SKILL.md).
WISH_ADVICE_AGENT_ID: int = 100000000000009
