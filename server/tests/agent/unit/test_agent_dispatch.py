"""Tests for U4: agent_dispatch._resolve_skills inline helper.

Per plan U4 + KD1, the skill resolution layer lives inline in agent_dispatch.py
as a module-level pure function. It enforces R5/R6/R15:
- R5: AI问答 (skills=["chat"]) → empty skill list (pure LLM mode)
- R6: 数鸣 (skills=["*"] sentinel) → all family-enabled skills
- R15: custom agent (skills=["report", ...]) → intersect with family-enabled

These tests run TEST-FIRST per the unit's Execution note.
"""

from apps.agent.services.agent_dispatch import _resolve_skills


# Helper: build a family enabled-skill list matching BackendClient.get_enabled_skills() shape.
def _enabled(*skill_ids: str) -> list[dict]:
    return [{"skill_id": sid, "skill_type": "builtin"} for sid in skill_ids]


# ── R5: AI问答 — chat-reserved capability returns empty ──────────────────────────


def test_chat_reserved_capability_returns_empty():
    """skills=['chat'] resolves to [] regardless of family-enabled skills."""
    family_enabled = _enabled("report", "allocation", "disposal")
    assert _resolve_skills(["chat"], family_enabled) == []


def test_chat_reserved_capability_returns_empty_even_with_no_family_skills():
    """skills=['chat'] resolves to [] when family has no enabled skills."""
    assert _resolve_skills(["chat"], []) == []


# ── R6: 数鸣 sentinel — wildcard returns all family-enabled ─────────────────────


def test_sentinel_returns_all_family_enabled_skills():
    """skills=['*'] resolves to the full family-enabled skill list."""
    family_enabled = _enabled("report", "allocation", "disposal")
    result = _resolve_skills(["*"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation", "disposal"}


def test_sentinel_with_zero_family_skills_returns_empty():
    """AE9: 数鸣 with sentinel + zero family skills → empty list (no error)."""
    assert _resolve_skills(["*"], []) == []


def test_sentinel_alongside_specific_skills_treated_as_wildcard():
    """If '*' appears anywhere in the list, treat as wildcard (per R6 spec)."""
    family_enabled = _enabled("report", "allocation")
    # Defensive: even if a custom agent accidentally includes "*", honor the sentinel
    result = _resolve_skills(["report", "*"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation"}


# ── R15: custom agent — intersect declared skills with family-enabled ───────────


def test_custom_agent_intersects_with_family_enabled():
    """custom agent skills are intersected with family-enabled skills."""
    family_enabled = _enabled("report", "allocation", "disposal", "liability")
    result = _resolve_skills(["report", "allocation"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation"}


def test_custom_agent_with_disabled_skill_returns_empty():
    """custom agent declaring a skill that family hasn't enabled gets empty intersection."""
    family_enabled = _enabled("allocation", "disposal")
    assert _resolve_skills(["report"], family_enabled) == []


def test_custom_agent_partial_intersection():
    """custom agent with mix of enabled + disabled skills gets only enabled subset."""
    family_enabled = _enabled("report", "disposal")
    result = _resolve_skills(["report", "allocation", "disposal"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "disposal"}


# ── Edge cases: empty / None / unexpected input ────────────────────────────────


def test_none_agent_skills_returns_empty():
    """agent.skills=None resolves to []."""
    family_enabled = _enabled("report", "allocation")
    assert _resolve_skills(None, family_enabled) == []


def test_empty_list_agent_skills_returns_empty():
    """agent.skills=[] resolves to []."""
    family_enabled = _enabled("report", "allocation")
    assert _resolve_skills([], family_enabled) == []


# ── Identity preservation: returned dicts match family list shape ──────────────


def test_resolved_skills_preserve_skill_dict_shape():
    """Resolved skills carry the same dict structure as the family-enabled list."""
    family_enabled = [
        {"skill_id": "report", "skill_type": "builtin"},
        {"skill_id": "allocation", "skill_type": "custom"},
    ]
    result = _resolve_skills(["report", "allocation"], family_enabled)
    assert len(result) == 2
    by_id = {s["skill_id"]: s for s in result}
    assert by_id["report"]["skill_type"] == "builtin"
    assert by_id["allocation"]["skill_type"] == "custom"


def test_sentinel_preserves_skill_dict_shape():
    """Sentinel resolution preserves all dict fields from family-enabled list."""
    family_enabled = [
        {"skill_id": "report", "skill_type": "builtin", "extra": "data"},
    ]
    result = _resolve_skills(["*"], family_enabled)
    assert result[0]["skill_id"] == "report"
    assert result[0]["skill_type"] == "builtin"
    assert result[0]["extra"] == "data"
