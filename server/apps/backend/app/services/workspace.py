"""WorkspaceService — per-family file storage under WORKSPACE_ROOT/{family_id}/.

Skill 文件布局对齐 DeerFlow 原生 UserScopedSkillStorage 约定（方案 A）：
custom skill 写入 ``{WORKSPACE_ROOT}/users/{family_id}/skills/custom/{skill_id}/SKILL.md``。
``WORKSPACE_ROOT`` 与 agent 的 ``AGENT_DATA_DIR`` / ``DEER_FLOW_HOME`` 同物理路径
（均派生自 ``DATA_ROOT/workspaces``），故 DeerFlow 运行时 ``UserScopedSkillStorage``
（按 ``get_effective_user_id() == family_id`` 解析 ``users/{fid}/skills/custom/``）
可直接读到本模块写入的文件，无需 symlink 桥接。

builtin skill 不允许家庭覆盖 prompt（决策 2）：家庭仅能创建 custom skill，
其 skill_id 由 ``RESERVED_NAMES`` 校验保证与 builtin 不重名。
"""

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
    """Legacy per-family skills dir (non-skill family files). Kept for backward compat."""
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


def skills_custom_dir(family_id: str) -> Path:
    """Return the DeerFlow-native custom skills directory for a family.

    Layout: ``{WORKSPACE_ROOT}/users/{family_id}/skills/custom/`` — matches
    DeerFlow ``UserScopedSkillStorage`` (which resolves
    ``{base_dir}/users/{user_id}/skills/custom/`` via ``get_paths()`` with
    ``user_id == family_id``). Writing here makes custom skills directly
    discoverable by DeerFlow's runtime skill scanner without symlink bridging.
    """
    d = Path(settings.WORKSPACE_ROOT) / "users" / str(family_id) / "skills" / "custom"
    d.mkdir(parents=True, exist_ok=True)
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
