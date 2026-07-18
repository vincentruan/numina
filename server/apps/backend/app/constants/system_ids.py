"""System agent and skill IDs — single source of truth for all runtime references.

These IDs are assigned at bootstrap time and must stay stable across deployments.
Alembic migration files use raw literals (historical snapshots) and are intentionally
excluded from this module — do not import from here in migration scripts.
"""

# System agent IDs (family_id=0, agent_type="system")
NUMINA_AGENT_ID: int = 100000000000005
ASSET_REPORT_AGENT_ID: int = 100000000000006

# System skill IDs (family_id=0, skill_type="builtin")
SKILL_REPORT_ID: int = 100000000000014
