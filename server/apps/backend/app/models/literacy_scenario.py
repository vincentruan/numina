# Re-export shim — implementation in packages/db/models/literacy_scenario.py
from packages.db.models.literacy_scenario import (  # noqa: F401
    LiteracyScenario,
    LiteracyScenarioTemplate,
)

__all__ = ["LiteracyScenario", "LiteracyScenarioTemplate"]
