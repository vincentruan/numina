"""SKILL.md frontmatter parser — extracts YAML metadata from skill files."""

import re
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_MAX_FRONTMATTER_SIZE = 4096  # 4KB cap to prevent YAML alias bombs


def parse_skill_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML frontmatter from SKILL.md content.

    Returns dict with keys: name, description, raw_frontmatter.
    On parse failure, returns None fallbacks without raising.
    """
    result: dict[str, Any] = {"name": None, "description": None, "raw_frontmatter": {}}

    if not content:
        return result

    match = _FRONTMATTER_RE.match(content)
    if not match:
        return result

    raw_yaml = match.group(1)
    if len(raw_yaml) > _MAX_FRONTMATTER_SIZE:
        return result

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return result

    if not isinstance(parsed, dict):
        return result

    result["raw_frontmatter"] = parsed
    result["name"] = parsed.get("name")
    result["description"] = parsed.get("description")
    return result


def validate_skill_content(content: str) -> bool:
    """Check that content has valid frontmatter with at least a name field."""
    if not content:
        return False
    parsed = parse_skill_frontmatter(content)
    return parsed["name"] is not None
