# Re-export shim — implementation moved to packages/db/models/child_economy/chore.py
from packages.db.models.child_economy.chore import (  # noqa: F401
    ChoreInstance,
    ChoreTemplate,
    chore_template_assignees,
)
