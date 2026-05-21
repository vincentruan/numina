"""WorkspaceService — per-family file storage under WORKSPACE_ROOT/{family_id}/."""

import shutil
from pathlib import Path

from apps.backend.app.config import settings


def _family_dir(family_id: str) -> Path:
    root = Path(settings.WORKSPACE_ROOT)
    d = root / str(family_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def images_dir(family_id: str) -> Path:
    d = _family_dir(family_id) / "images"
    d.mkdir(exist_ok=True)
    return d


def skills_dir(family_id: str) -> Path:
    d = _family_dir(family_id) / "skills"
    d.mkdir(exist_ok=True)
    return d


def prompts_dir(family_id: str) -> Path:
    d = _family_dir(family_id) / "prompts"
    d.mkdir(exist_ok=True)
    return d


def exports_dir(family_id: str) -> Path:
    d = _family_dir(family_id) / "exports"
    d.mkdir(exist_ok=True)
    return d


def get_skill_prompt(family_id: str, capability: str) -> str | None:
    """Return custom skill prompt from workspace if it exists, else None."""
    skill_file = skills_dir(family_id) / f"{capability}.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return None


def save_skill_prompt(family_id: str, capability: str, content: str) -> None:
    """Write a custom skill prompt to the workspace."""
    skill_file = skills_dir(family_id) / f"{capability}.md"
    skill_file.write_text(content, encoding="utf-8")


def delete_skill_prompt(family_id: str, capability: str) -> None:
    """Remove a custom skill prompt from the workspace (no-op if absent)."""
    skill_file = skills_dir(family_id) / f"{capability}.md"
    skill_file.unlink(missing_ok=True)


def skills_custom_dir(family_id: str) -> Path:
    """Return custom skills directory for a family: WORKSPACE_ROOT/{family_id}/skills_custom/."""
    d = _family_dir(family_id) / "skills_custom"
    d.mkdir(exist_ok=True)
    return d


def get_custom_skill_file(family_id: str, skill_id: str) -> Path:
    """Return path to a custom skill SKILL.md file."""
    return skills_custom_dir(family_id) / skill_id / "SKILL.md"


def create_custom_skill(family_id: str, skill_id: str, content: str) -> Path:
    """Create a custom skill directory and write SKILL.md content."""
    skill_dir = skills_custom_dir(family_id) / skill_id
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def delete_custom_skill(family_id: str, skill_id: str) -> None:
    """Remove a custom skill directory (no-op if absent)."""
    skill_dir = skills_custom_dir(family_id) / skill_id
    if skill_dir.exists():
        shutil.rmtree(skill_dir)


def chat_prompt_file(family_id: str) -> Path:
    """Return the path to the family's chat prompt override file."""
    return prompts_dir(family_id) / "chat.md"


def get_chat_prompt(family_id: str) -> str | None:
    """Return family's chat prompt override content (body only, no frontmatter), or None."""
    f = chat_prompt_file(family_id)
    if not f.exists():
        return None
    return _strip_frontmatter(f.read_text(encoding="utf-8"))


def save_chat_prompt(family_id: str, content: str) -> None:
    """Write family's chat prompt override file."""
    chat_prompt_file(family_id).write_text(content, encoding="utf-8")


def delete_chat_prompt(family_id: str) -> None:
    """Remove family's chat prompt override file (no-op if absent)."""
    chat_prompt_file(family_id).unlink(missing_ok=True)


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a markdown string, return body only."""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
