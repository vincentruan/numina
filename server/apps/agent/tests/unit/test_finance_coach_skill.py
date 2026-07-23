"""finance-coach SKILL.md frontmatter + allowed-tools base-name convention."""
from pathlib import Path

import yaml

SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "builtin" / "public" / "finance-coach" / "SKILL.md"
)


def _parse_frontmatter() -> dict:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with frontmatter"
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])  # type: ignore[no-any-return]  # yaml.safe_load returns Any; frontmatter is always a dict


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"finance-coach SKILL.md missing at {SKILL_PATH}"


def test_frontmatter_name_and_description():
    fm = _parse_frontmatter()
    assert fm["name"] == "finance-coach"
    assert "财务" in fm["description"]


def test_allowed_tools_use_base_names_not_prefixed():
    """U4 pilot bug: filter_tools_by_skill_allowed_tools does full-name exact
    match, NOT prefix match. allowed-tools must use base names (get_assets),
    not numina-prefixed (numina-get_assets), or all business tools get filtered
    out and the agent hits RecursionError."""
    fm = _parse_frontmatter()
    tools = fm["allowed-tools"]
    assert "get_assets" in tools
    assert "get_liabilities" in tools
    assert "get_members" in tools
    # CRITICAL: no numina- prefixed entries
    for t in tools:
        assert not t.startswith("numina-"), f"allowed-tools must use base name, got prefixed: {t}"


def test_thinking_disabled():
    """finance-coach is a single-run stateless advice agent — thinking=False
    mirrors asset-report/import-parse (keeps latency + token cost bounded)."""
    fm = _parse_frontmatter()
    assert fm.get("thinking") is False
