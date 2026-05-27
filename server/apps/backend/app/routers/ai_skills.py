"""技能配置管理路由（per-family）。

Skill catalog 命名空间约定：
- ``BUILTIN_CAPABILITIES`` 列出可启用/禁用的业务能力 skill（对应 ``agent/skills/*.md`` 文件）。
- ``RESERVED_NAMES`` 保留给系统内部能力，禁止 owner 创建同名 custom skill：
  - ``chat`` 是 AI 问答智能体的纯 LLM 对话内部能力（``agent.skills=["chat"]`` 由 dispatch 层
    识别为"无业务 skill"模式，不进入 catalog 查找）。
- ``time_machine`` 是固定规则计算应用，作为独立 ``/ai/time-machine`` 页面入口暴露，不作为可调度 skill。

"""

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family_skill_config import FamilySkillConfig
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.user import User
from apps.backend.app.services import workspace

router = APIRouter(prefix="/ai/skills", tags=["ai-skills"])
logger = logging.getLogger(__name__)

# Business capabilities exposed to skill management (matches agent/skills/*.md).
# 注意：`chat` 与 `time_machine` 不在此列 — 见 RESERVED_NAMES。
BUILTIN_CAPABILITIES = [
    "report",
    "alerts",
    "allocation",
    "disposal",
    "liability",
    "spending_leak",
]

# Reserved namespace — not skills, but blocked from custom skill_id collisions.
RESERVED_NAMES = ["chat", "time_machine"]

BUILTIN_DEFAULT_ORDER = {
    "report": 100,
    "alerts": 101,
    "allocation": 102,
    "disposal": 103,
    "liability": 104,
    "spending_leak": 105,
}

SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

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
            return str(ws_prompt.strip())
    skill_file = _SKILLS_DIR / f"{capability}.md"
    if not skill_file.exists():
        return None
    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3 :].strip()
    return content.strip()


# ── Schemas ───────────────────────────────────────────────────────────────────


class SkillConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capability: str
    is_enabled: bool
    custom_prompt: str | None
    default_prompt: (
        str | None
    )  # always populated from workspace override or skills/*.md


class SkillConfigUpdate(BaseModel):
    is_enabled: bool | None = None
    custom_prompt: str | None = None  # None = keep existing; "" = clear override


class SkillDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    skill_type: str
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    route: str | None = None
    input_mode: str | None = None
    examples: list[str] | None = None
    is_enabled: bool = True
    display_order: int = 0
    can_edit: bool = False
    can_delete: bool = False


class SkillListGroupedResponse(BaseModel):
    fixed: list[SkillDefinitionResponse]
    builtin: list[SkillDefinitionResponse]
    custom: list[SkillDefinitionResponse]


class CustomSkillCreate(BaseModel):
    skill_id: str
    name: str
    description: str | None = None
    icon: str
    color: str
    input_mode: str = "trigger"
    examples: list[str] | None = None
    prompt_content: str

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, v: str) -> str:
        if not SKILL_ID_PATTERN.match(v):
            raise ValueError(
                "skill_id 只能包含小写字母、数字、下划线、连字符，且不能数字开头"
            )
        if len(v) > 64:
            raise ValueError("skill_id 长度不能超过 64 字符")
        if v in BUILTIN_CAPABILITIES:
            raise ValueError("skill_id 不能与内置技能冲突")
        if v in RESERVED_NAMES:
            raise ValueError("skill_id 与保留命名冲突")
        return v


class CustomSkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    input_mode: str | None = None
    examples: list[str] | None = None
    prompt_content: str | None = None


class TogglePayload(BaseModel):
    is_enabled: bool


class ReorderRequest(BaseModel):
    skill_ids: list[str]


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

    row = (
        db.query(FamilySkillConfig)
        .filter(
            FamilySkillConfig.family_id == current_user.family_id,
            FamilySkillConfig.capability == capability,
        )
        .first()
    )

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

    row = (
        db.query(FamilySkillConfig)
        .filter(
            FamilySkillConfig.family_id == current_user.family_id,
            FamilySkillConfig.capability == capability,
        )
        .first()
    )

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


# ── New Endpoints: Grouped, Custom CRUD, Toggle, Reorder ───────────────────────


@router.get("/grouped", response_model=SkillListGroupedResponse)
def list_skills_grouped(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SkillListGroupedResponse:
    """获取分组技能列表（fixed/builtin/custom）。"""
    family_id = current_user.family_id
    db_records = {
        r.skill_id: r
        for r in db.query(SkillRegistry)
        .filter(SkillRegistry.family_id == family_id)
        .all()
    }

    fixed: list[SkillDefinitionResponse] = []

    builtin = []
    for skill_id in BUILTIN_CAPABILITIES:
        record = db_records.get(skill_id)
        is_enabled = record.is_enabled if record else True
        display_order = (
            record.display_order if record else BUILTIN_DEFAULT_ORDER.get(skill_id, 100)
        )
        builtin.append(
            SkillDefinitionResponse(
                id=skill_id,
                skill_type="builtin",
                display_order=display_order,
                is_enabled=is_enabled,
            )
        )
    builtin.sort(key=lambda s: s.display_order)

    custom = []
    for record in (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_type == "custom",
        )
        .order_by(SkillRegistry.display_order)
        .all()
    ):
        custom.append(
            SkillDefinitionResponse(
                id=record.skill_id,
                skill_type="custom",
                name=record.name,
                description=record.description,
                icon=record.icon,
                color=record.color,
                route=record.route,
                input_mode=record.input_mode,
                examples=record.examples,
                display_order=record.display_order,
                is_enabled=record.is_enabled,
                can_edit=True,
                can_delete=True,
            )
        )

    return SkillListGroupedResponse(fixed=fixed, builtin=builtin, custom=custom)


@router.post("/custom", response_model=SkillDefinitionResponse)
def create_custom_skill_endpoint(
    payload: CustomSkillCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinitionResponse:
    """创建自定义技能。"""
    family_id = current_user.family_id
    existing = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == payload.skill_id,
        )
        .first()
    )
    if existing:
        raise AppError(
            ErrorCode.VALIDATION_ERROR, f"技能 ID '{payload.skill_id}' 已存在"
        )

    max_order = (
        db.query(func.max(SkillRegistry.display_order))
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_type == "custom",
        )
        .scalar()
        or 199
    )
    display_order = max_order + 1

    skill_md_content = f"---\nname: {payload.name}\ndescription: {payload.description or ''}\ntrigger_phrases:\n  - {payload.name}\nallowed-tools: []\nthinking: false\n---\n\n{payload.prompt_content}\n"
    workspace.create_custom_skill(str(family_id), payload.skill_id, skill_md_content)

    record = SkillRegistry(
        family_id=family_id,
        skill_id=payload.skill_id,
        skill_type="custom",
        name=payload.name,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        input_mode=payload.input_mode,
        examples=payload.examples,
        is_enabled=True,
        display_order=display_order,
        created_by=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return SkillDefinitionResponse(
        id=record.skill_id,
        skill_type="custom",
        name=record.name,
        description=record.description,
        icon=record.icon,
        color=record.color,
        input_mode=record.input_mode,
        examples=record.examples,
        display_order=record.display_order,
        is_enabled=record.is_enabled,
        can_edit=True,
        can_delete=True,
    )


@router.put("/reorder")
def reorder_skills_endpoint(
    payload: ReorderRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """批量调整排序。"""
    family_id = current_user.family_id
    for idx, skill_id in enumerate(payload.skill_ids):
        record = (
            db.query(SkillRegistry)
            .filter(
                SkillRegistry.family_id == family_id,
                SkillRegistry.skill_id == skill_id,
            )
            .first()
        )
        if not record:
            if skill_id in BUILTIN_CAPABILITIES:
                record = SkillRegistry(
                    family_id=family_id,
                    skill_id=skill_id,
                    skill_type="builtin",
                    display_order=idx,
                    is_enabled=True,
                )
                db.add(record)
        else:
            record.display_order = idx
    db.commit()
    return {"ok": True}


@router.put("/{skill_id}/toggle", response_model=SkillDefinitionResponse)
def toggle_skill_endpoint(
    skill_id: str,
    payload: TogglePayload,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinitionResponse:
    """启用/禁用技能。"""
    family_id = current_user.family_id

    record = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == skill_id,
        )
        .first()
    )

    if not record:
        if skill_id in BUILTIN_CAPABILITIES:
            record = SkillRegistry(
                family_id=family_id,
                skill_id=skill_id,
                skill_type="builtin",
                is_enabled=payload.is_enabled,
                display_order=BUILTIN_DEFAULT_ORDER.get(skill_id, 100),
            )
            db.add(record)
        else:
            raise AppError(ErrorCode.NOT_FOUND, f"技能 '{skill_id}' 不存在")
    else:
        record.is_enabled = payload.is_enabled

    db.commit()
    db.refresh(record)

    return SkillDefinitionResponse(
        id=skill_id,
        skill_type=record.skill_type,
        display_order=record.display_order,
        is_enabled=record.is_enabled,
        name=record.name,
        description=record.description,
        icon=record.icon,
        color=record.color,
        input_mode=record.input_mode,
        examples=record.examples,
        can_edit=record.skill_type == "custom",
        can_delete=record.skill_type == "custom",
    )


@router.put("/custom/{skill_id}", response_model=SkillDefinitionResponse)
def update_custom_skill_endpoint(
    skill_id: str,
    payload: CustomSkillUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinitionResponse:
    """更新自定义技能。"""
    family_id = current_user.family_id
    record = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == skill_id,
            SkillRegistry.skill_type == "custom",
        )
        .first()
    )
    if not record:
        raise AppError(ErrorCode.NOT_FOUND, f"自定义技能 '{skill_id}' 不存在")

    if payload.name is not None:
        record.name = payload.name
    if payload.description is not None:
        record.description = payload.description
    if payload.icon is not None:
        record.icon = payload.icon
    if payload.color is not None:
        record.color = payload.color
    if payload.input_mode is not None:
        record.input_mode = payload.input_mode
    if payload.examples is not None:
        record.examples = payload.examples

    if payload.prompt_content is not None:
        skill_md_content = f"---\nname: {record.name}\ndescription: {record.description or ''}\ntrigger_phrases:\n  - {record.name}\nallowed-tools: []\nthinking: false\n---\n\n{payload.prompt_content}\n"
        workspace.create_custom_skill(str(family_id), skill_id, skill_md_content)

    db.commit()
    db.refresh(record)

    return SkillDefinitionResponse(
        id=record.skill_id,
        skill_type="custom",
        name=record.name,
        description=record.description,
        icon=record.icon,
        color=record.color,
        input_mode=record.input_mode,
        examples=record.examples,
        display_order=record.display_order,
        is_enabled=record.is_enabled,
        can_edit=True,
        can_delete=True,
    )


@router.delete("/custom/{skill_id}")
def delete_custom_skill_endpoint(
    skill_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """删除自定义技能。"""
    family_id = current_user.family_id
    record = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == skill_id,
            SkillRegistry.skill_type == "custom",
        )
        .first()
    )
    if not record:
        raise AppError(ErrorCode.NOT_FOUND, f"自定义技能 '{skill_id}' 不存在")

    db.delete(record)
    db.commit()
    workspace.delete_custom_skill(str(family_id), skill_id)
    return {"ok": True}
