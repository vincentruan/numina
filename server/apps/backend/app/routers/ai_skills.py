"""技能配置管理路由（per-family）。

Skill catalog 命名空间约定：
- ``RESERVED_NAMES`` 保留给系统内部能力，禁止 owner 创建同名 custom skill：
  - ``chat`` 是 AI 问答智能体的纯 LLM 对话内部能力（``agent.skills=["chat"]`` 由 dispatch 层
    识别为"无业务 skill"模式，不进入 catalog 查找）。
  - ``asset-report`` 是系统内置固定流程（三步流水线，KTD-8），有独立 skill 目录但不可开关。
- ``time_machine`` 已从 skill 系统解耦（KTD-9，非 AI 纯计算应用），保留为独立
  ``/ai/time-machine`` 页面入口，不再占 RESERVED_NAMES。

"""

import logging
import re

import httpx
import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.user import User
from apps.backend.app.services import workspace
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.skill_command_parser import SkillCommandParser
from apps.backend.app.services.skill_downloader import (
    SkillDownloader,
    SkillDownloadError,
)
from apps.backend.app.services.skill_parser import parse_skill_frontmatter

router = APIRouter(prefix="/ai/skills", tags=["ai-skills"])
logger = logging.getLogger(__name__)

# Reserved namespace — not skills, but blocked from custom skill_id collisions.
# - ``chat`` 是 AI 问答智能体的纯 LLM 对话内部能力（``agent.skills=["chat"]`` 由
#   dispatch 层识别为"无业务 skill"模式，不进入 catalog 查找）。
# - ``asset-report`` 是系统内置固定流程（三步流水线，KTD-8），有独立 skill 目录
#   放 prompt 但用户不可开关、不可创建同名 custom skill。
# U5/KTD-9: ``time_machine`` 已移除（非 AI skill，纯计算应用，从 skill 系统解耦）。
# U8: ``import-parse`` 加入（系统内置固定流程：金融文档持仓解析，KTD-8）。
# Plan A: ``finance-coach`` 加入（系统内置固定流程：家庭财务处方建议，KTD-8）。
RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach"]

# Internal-only skills excluded from user-facing catalog and creation.
INTERNAL_ONLY_SKILLS = {"skill-creator", "skill-installer"}


SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def _build_skill_md(name: str, description: str | None, prompt_content: str) -> str:
    frontmatter = yaml.dump(
        {
            "name": name,
            "description": description or "",
            "trigger_phrases": [name],
            "allowed-tools": [],
            "thinking": False,
        },
        default_flow_style=False,
        allow_unicode=True,
    )
    return f"---\n{frontmatter}---\n\n{prompt_content}\n"


def _strip_allowed_tools(content: str) -> str:
    stripped = re.sub(r"^[ \t]*allowed-tools:.*$(?:\n[ \t]+-.*)*", "", content, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", stripped)


# ── Schemas ───────────────────────────────────────────────────────────────────


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

    @field_validator("prompt_content")
    @classmethod
    def validate_prompt_content_size(cls, v: str) -> str:
        if len(v) > 65536:
            raise ValueError("提示词内容不能超过 64KB")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if "\n" in v or "\r" in v:
            raise ValueError("名称不能包含换行符")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None and ("\n" in v or "\r" in v):
            raise ValueError("描述不能包含换行符")
        return v

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, v: str) -> str:
        if not SKILL_ID_PATTERN.match(v):
            raise ValueError(
                "skill_id 只能包含小写字母、数字、下划线、连字符，且不能数字开头"
            )
        if len(v) > 64:
            raise ValueError("skill_id 长度不能超过 64 字符")
        if v in RESERVED_NAMES:
            raise ValueError("skill_id 与保留命名冲突")
        if v in INTERNAL_ONLY_SKILLS:
            raise ValueError("skill_id 与系统内部技能冲突")
        return v


class CustomSkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    input_mode: str | None = None
    examples: list[str] | None = None
    prompt_content: str | None = None


class InstallRequest(BaseModel):
    command: str


class AICreateRequest(BaseModel):
    description: str

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("描述不能为空")
        if len(v) > 4096:
            raise ValueError("描述长度不能超过 4096 字符")
        return v


class AICreateResponse(BaseModel):
    content: str
    parsed_name: str | None = None
    parsed_description: str | None = None


class RawSkillSaveRequest(BaseModel):
    skill_id: str
    content: str
    icon: str = "⚡"
    color: str = "#007aff"

    @field_validator("content")
    @classmethod
    def validate_content_size(cls, v: str) -> str:
        if len(v) > 65536:
            raise ValueError("技能内容不能超过 64KB")
        return v

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, v: str) -> str:
        if not SKILL_ID_PATTERN.match(v):
            raise ValueError(
                "skill_id 只能包含小写字母、数字、下划线、连字符，且不能数字开头"
            )
        if len(v) > 64:
            raise ValueError("skill_id 长度不能超过 64 字符")
        if v in RESERVED_NAMES:
            raise ValueError("skill_id 与保留命名冲突")
        if v in INTERNAL_ONLY_SKILLS:
            raise ValueError("skill_id 与内部技能冲突")
        return v


class TogglePayload(BaseModel):
    is_enabled: bool


class ReorderRequest(BaseModel):
    skill_ids: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────


# ── New Endpoints: Grouped, Custom CRUD, Toggle, Reorder ───────────────────────


@router.get("/grouped", response_model=SkillListGroupedResponse)
def list_skills_grouped(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SkillListGroupedResponse:
    """获取分组技能列表（fixed/builtin/custom）。"""
    family_id = current_user.family_id

    fixed: list[SkillDefinitionResponse] = []

    builtin: list[SkillDefinitionResponse] = []

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

    skill_md_content = _build_skill_md(payload.name, payload.description, payload.prompt_content)

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

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)

    try:
        workspace.create_custom_skill(str(family_id), payload.skill_id, skill_md_content)
    except Exception:
        db.delete(record)
        db.commit()
        raise

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
        if record:
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
    if skill_id in RESERVED_NAMES:
        raise AppError(ErrorCode.NOT_FOUND, f"技能 '{skill_id}' 不存在")

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
        skill_md_content = _build_skill_md(record.name, record.description, payload.prompt_content)
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


@router.post("/install", response_model=SkillDefinitionResponse)
async def install_skill_endpoint(
    payload: InstallRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinitionResponse:
    """通过命令安装技能。支持 CLI 命令、GitHub/skills.sh URL，以及 AI 回退。"""
    family_id = current_user.family_id

    # Step 1: Parse command
    parser = SkillCommandParser()
    parse_result = parser.parse(payload.command)

    # Step 2: Download or AI fallback
    content: str
    source_url: str | None
    skill_id: str

    if parse_result.match_type in ("cli", "url"):
        downloader = SkillDownloader()
        try:
            download_result = await downloader.download(parse_result)
        except SkillDownloadError as e:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, f"下载技能失败: {e}")
        content = download_result.content
        source_url = download_result.source_url
        skill_id = download_result.skill_id
    else:
        # AI fallback: call skill-installer via agent service
        try:
            agent_client = AgentClient(family_id, current_user.id, timeout=60.0)
            resp = await agent_client.post(
                "/internal/gateway/skill-dispatch",
                json={
                    "skill_name": "skill-installer",
                    "family_id": str(family_id),
                    "input_text": payload.command,
                },
            )
            if resp.status_code == 504:
                raise AppError(ErrorCode.AI_SERVICE_TIMEOUT, "AI 安装超时，请稍后重试")
            if resp.status_code >= 400:
                raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, f"AI 安装失败: {resp.text}")
            body = resp.json()
            content = body.get("content")
            if not content:
                raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, "AI 安装返回内容为空")
        except httpx.TimeoutException:
            raise AppError(ErrorCode.AI_SERVICE_TIMEOUT, "AI 安装超时，请稍后重试")
        except httpx.HTTPError as e:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, f"AI 安装请求失败: {e}")
        source_url = None

    # Step 3: Parse frontmatter
    frontmatter = parse_skill_frontmatter(content)
    name = frontmatter["name"]
    description = frontmatter["description"]

    # Step 4: Derive skill_id (for AI fallback, extract from frontmatter name)
    if parse_result.match_type == "unmatched":
        raw_name = name or "unnamed-skill"
        skill_id = re.sub(r"[^a-z0-9_-]", "-", raw_name.lower()).strip("-")
        if not skill_id or not SKILL_ID_PATTERN.match(skill_id):
            skill_id = "custom-skill"

    # Step 5: Validate skill_id
    if not SKILL_ID_PATTERN.match(skill_id):
        raise AppError(ErrorCode.VALIDATION_ERROR, f"非法技能标识符: {skill_id}")
    if skill_id in RESERVED_NAMES or skill_id in INTERNAL_ONLY_SKILLS:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"技能 ID '{skill_id}' 与内置/保留/内部技能冲突")

    # Step 6: Filesystem confinement guard
    skill_dir = workspace.skills_custom_dir(str(family_id)) / skill_id
    base_dir = workspace.skills_custom_dir(str(family_id)).resolve()
    if not skill_dir.resolve().is_relative_to(base_dir):
        raise AppError(ErrorCode.VALIDATION_ERROR, "非法技能路径")

    # Step 7: DB write first (within transaction)
    existing = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == skill_id,
        )
        .first()
    )
    if existing:
        raise AppError(ErrorCode.VALIDATION_ERROR, "该技能已存在")

    max_order = (
        db.query(func.max(SkillRegistry.display_order))
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_type == "custom",
        )
        .scalar()
        or 199
    )

    record = SkillRegistry(
        family_id=family_id,
        skill_id=skill_id,
        skill_type="custom",
        name=name or skill_id,
        description=description,
        is_enabled=True,
        display_order=max_order + 1,
        creation_type="cmd",
        source_url=source_url,
        created_by=current_user.id,
    )
    db.add(record)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)

    # Step 8: Filesystem write (after DB commit)
    try:
        workspace.create_custom_skill(str(family_id), skill_id, _strip_allowed_tools(content))
    except Exception:
        # Compensating transaction: delete the DB row
        db.delete(record)
        db.commit()
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, "技能文件写入失败")

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


@router.post("/ai-create", response_model=AICreateResponse)
async def ai_create_skill_endpoint(
    payload: AICreateRequest,
    current_user: User = Depends(require_owner),
) -> AICreateResponse:
    """AI 生成技能预览（不保存）。调用 skill-creator 生成标准 SKILL.md。"""
    family_id = current_user.family_id

    try:
        agent_client = AgentClient(family_id, current_user.id, timeout=60.0)
        resp = await agent_client.post(
            "/internal/gateway/skill-dispatch",
            json={
                "skill_name": "skill-creator",
                "family_id": str(family_id),
                "input_text": payload.description,
            },
        )
        if resp.status_code == 504:
            raise AppError(ErrorCode.AI_SERVICE_TIMEOUT, "AI 生成超时，请稍后重试")
        if resp.status_code >= 400:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, f"AI 生成失败: {resp.text}")
        body = resp.json()
        content = body.get("content")
        if not content:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, "AI 生成返回内容为空")
    except AppError:
        raise
    except httpx.TimeoutException:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT, "AI 生成超时，请稍后重试")
    except httpx.HTTPError as e:
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, f"AI 生成请求失败: {e}")

    # Validate content size
    if len(content.encode("utf-8")) > 64 * 1024:
        raise AppError(ErrorCode.VALIDATION_ERROR, "AI 生成内容过大")

    # Parse frontmatter (best-effort — return even if malformed)
    frontmatter = parse_skill_frontmatter(content)

    return AICreateResponse(
        content=content,
        parsed_name=frontmatter["name"],
        parsed_description=frontmatter["description"],
    )


@router.post("/custom/raw", response_model=SkillDefinitionResponse)
def save_raw_skill_endpoint(
    payload: RawSkillSaveRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinitionResponse:
    """保存 AI 生成或命令安装的原始 SKILL.md 内容（保留结构）。"""
    family_id = current_user.family_id

    # Parse frontmatter from raw content
    frontmatter = parse_skill_frontmatter(payload.content)
    name = frontmatter["name"] or payload.skill_id
    description = frontmatter["description"]

    # Filesystem confinement guard
    skill_dir = workspace.skills_custom_dir(str(family_id)) / payload.skill_id
    base_dir = workspace.skills_custom_dir(str(family_id)).resolve()
    if not skill_dir.resolve().is_relative_to(base_dir):
        raise AppError(ErrorCode.VALIDATION_ERROR, "非法技能路径")

    # DB write first
    existing = (
        db.query(SkillRegistry)
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == payload.skill_id,
        )
        .first()
    )
    if existing:
        raise AppError(ErrorCode.VALIDATION_ERROR, "该技能已存在")

    max_order = (
        db.query(func.max(SkillRegistry.display_order))
        .filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_type == "custom",
        )
        .scalar()
        or 199
    )

    record = SkillRegistry(
        family_id=family_id,
        skill_id=payload.skill_id,
        skill_type="custom",
        name=name,
        description=description,
        icon=payload.icon,
        color=payload.color,
        is_enabled=True,
        display_order=max_order + 1,
        creation_type="ai_created",
        created_by=current_user.id,
    )
    db.add(record)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)

    # Filesystem write after DB commit
    try:
        workspace.create_custom_skill(str(family_id), payload.skill_id, _strip_allowed_tools(payload.content))
    except Exception:
        db.delete(record)
        db.commit()
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, "技能文件写入失败")

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
