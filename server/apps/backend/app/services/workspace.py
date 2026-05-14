"""WorkspaceService — per-family file storage under WORKSPACE_ROOT/{family_id}/."""
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
