"""技能配置管理路由（per-family）。"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.deps import require_adult, require_owner
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.family_skill_config import FamilySkillConfig
from app.models.user import User
from app.services import workspace

router = APIRouter(prefix="/ai/skills", tags=["ai-skills"])
logger = logging.getLogger(__name__)

# Canonical list of built-in capabilities (matches agent/skills/*.md)
BUILTIN_CAPABILITIES = [
    "report",
    "chat",
    "alerts",
    "allocation",
    "disposal",
    "liability",
    "spending_leak",
    "time_machine",
]

# Resolve skills directory: prefer AGENT_SKILLS_DIR env var (set in docker-compose /
# production), fall back to the sibling agent/skills/ path for local dev.
_env_skills_dir = os.environ.get("AGENT_SKILLS_DIR")
_SKILLS_DIR: Path = (
    Path(_env_skills_dir)
    if _env_skills_dir
    else Path(__file__).parent.parent.parent.parent.parent / "agent" / "skills"
)


def _read_default_prompt(capability: str, family_id: str | None = None) -> str | None:
    """Read skill prompt: workspace override first, then agent/skills/{capability}.md."""
    if family_id is not None:
        ws_prompt = workspace.get_skill_prompt(family_id, capability)
        if ws_prompt is not None:
            return ws_prompt.strip()
    skill_file = _SKILLS_DIR / f"{capability}.md"
    if not skill_file.exists():
        return None
    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SkillConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capability: str
    is_enabled: bool
    custom_prompt: str | None
    default_prompt: str | None  # always populated from workspace override or skills/*.md


class SkillConfigUpdate(BaseModel):
    is_enabled: bool | None = None
    custom_prompt: str | None = None  # None = keep existing; "" = clear override


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SkillConfigResponse])
def list_skills(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[SkillConfigResponse]:
    """列出所有内置技能及当前家庭的配置状态。"""
    rows = {
        r.capability: r
        for r in db.query(FamilySkillConfig)
        .filter(FamilySkillConfig.family_id == current_user.family_id)
        .all()
    }
    result = []
    for cap in BUILTIN_CAPABILITIES:
        row = rows.get(cap)
        default_prompt = _read_default_prompt(cap, current_user.family_id)
        result.append(
            SkillConfigResponse(
                capability=cap,
                is_enabled=row.is_enabled if row else True,
                custom_prompt=row.custom_prompt if row else None,
                default_prompt=default_prompt,
            )
        )
    return result


@router.put("/{capability}", response_model=SkillConfigResponse)
def update_skill(
    capability: str,
    payload: SkillConfigUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillConfigResponse:
    """更新技能配置（仅 owner）。空字符串 custom_prompt 表示清除自定义提示词。"""
    if capability not in BUILTIN_CAPABILITIES:
        raise AppError(ErrorCode.NOT_FOUND, f"未知技能: {capability}")

    row = db.query(FamilySkillConfig).filter(
        FamilySkillConfig.family_id == current_user.family_id,
        FamilySkillConfig.capability == capability,
    ).first()

    if row is None:
        row = FamilySkillConfig(
            family_id=current_user.family_id,
            capability=capability,
            is_enabled=True,
            custom_prompt=None,
        )
        db.add(row)

    if payload.is_enabled is not None:
        row.is_enabled = payload.is_enabled
    if payload.custom_prompt is not None:
        # Empty string clears the override; non-empty sets it
        row.custom_prompt = payload.custom_prompt if payload.custom_prompt else None

    db.commit()
    db.refresh(row)

    default_prompt = _read_default_prompt(capability, current_user.family_id)
    return SkillConfigResponse(
        capability=row.capability,
        is_enabled=row.is_enabled,
        custom_prompt=row.custom_prompt,
        default_prompt=default_prompt,
    )


@router.delete("/{capability}/prompt", response_model=SkillConfigResponse)
def reset_skill_prompt(
    capability: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillConfigResponse:
    """重置技能提示词为默认值（仅 owner）。"""
    if capability not in BUILTIN_CAPABILITIES:
        raise AppError(ErrorCode.NOT_FOUND, f"未知技能: {capability}")

    row = db.query(FamilySkillConfig).filter(
        FamilySkillConfig.family_id == current_user.family_id,
        FamilySkillConfig.capability == capability,
    ).first()

    if row:
        row.custom_prompt = None
        db.commit()
        db.refresh(row)

    default_prompt = _read_default_prompt(capability, current_user.family_id)
    return SkillConfigResponse(
        capability=capability,
        is_enabled=row.is_enabled if row else True,
        custom_prompt=None,
        default_prompt=default_prompt,
    )
