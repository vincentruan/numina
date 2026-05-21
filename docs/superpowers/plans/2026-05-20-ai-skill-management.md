# AI 技能管理系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 能力分为三类（固定、内置、自定义），支持家庭租户隔离的技能管理，用户可在设置中启用/禁用/新增技能。

**Architecture:** DeerFlow 文件加载机制不变，通过数据库 skill_registry 表管理启用/禁用/排序配置，CapabilityRegistry 查询数据库过滤禁用技能。目录结构迁移到 builtin/ + custom/{family_id}/ 方案。

**Tech Stack:** Python (FastAPI, SQLAlchemy, Alembic), Vue 3 (TypeScript), DeerFlow 2.0

---

## 文件结构总览

### 新建文件

| 文件 | 职责 |
|------|------|
| `server/apps/backend/app/models/skill_registry.py` | 数据库模型定义 |
| `server/apps/backend/alembic/versions/xxx_add_skill_registry_table.py` | 数据库迁移 |
| `server/apps/agent/skills/builtin/*/SKILL.md` | 迁移后的内置技能文件 |

### 修改文件

| 文件 | 改动内容 |
|------|---------|
| `server/apps/backend/app/routers/ai_skills.py` | 扩展支持 custom 技能 CRUD、排序 API |
| `server/apps/backend/app/services/workspace.py` | 新增 skills_custom_dir 函数 |
| `server/apps/backend/app/models/__init__.py` | 导入新模型 |
| `server/apps/agent/services/capability_registry.py` | 扩展合并扫描逻辑 |
| `frontend/apps/main/src/pages/AIHubPage.vue` | 三段展示改造 |
| `frontend/apps/main/src/pages/SkillsManagePage.vue` | 新增/编辑/删除/排序功能 |
| `frontend/apps/main/src/api/ai.ts` | 新增技能 API |
| `frontend/apps/main/src/stores/capability.ts` | 扩展支持 skill_type |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | 内置技能 i18n 配置 |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | 内置技能 i18n 配置 |

---

## Task 1: 目录结构迁移

**Files:**
- Create: `server/apps/agent/skills/builtin/alerts/SKILL.md`
- Create: `server/apps/agent/skills/builtin/allocation/SKILL.md`
- Create: `server/apps/agent/skills/builtin/chat/SKILL.md`
- Create: `server/apps/agent/skills/builtin/disposal/SKILL.md`
- Create: `server/apps/agent/skills/builtin/liability/SKILL.md`
- Create: `server/apps/agent/skills/builtin/report/SKILL.md`
- Create: `server/apps/agent/skills/builtin/spending_leak/SKILL.md`
- Create: `server/apps/agent/skills/builtin/time_machine/SKILL.md`
- Delete: `server/apps/agent/skills/*.md` (旧元数据文件)
- Modify: `server/apps/agent/deerflow_config/base/config.yaml`

- [ ] **Step 1: 创建 builtin 目录并移动 SKILL.md 文件**

```bash
cd server/apps/agent/skills
mkdir -p builtin/alerts builtin/allocation builtin/chat builtin/disposal builtin/liability builtin/report builtin/spending_leak builtin/time_machine

# 移动现有 custom 目录下的 SKILL.md 到 builtin
mv custom/alerts/SKILL.md builtin/alerts/SKILL.md
mv custom/allocation/SKILL.md builtin/allocation/SKILL.md
mv custom/chat/SKILL.md builtin/chat/SKILL.md
mv custom/disposal/SKILL.md builtin/disposal/SKILL.md
mv custom/liability/SKILL.md builtin/liability/SKILL.md
mv custom/report/SKILL.md builtin/report/SKILL.md
mv custom/spending_leak/SKILL.md builtin/spending_leak/SKILL.md
mv custom/time_machine/SKILL.md builtin/time_machine/SKILL.md
```

- [ ] **Step 2: 删除旧的元数据文件**

```bash
cd server/apps/agent/skills
rm -f alerts.md allocation.md chat.md disposal.md liability.md report.md spending_leak.md time_machine.md
```

- [ ] **Step 3: 删除 custom 目录下已迁移的技能目录**

```bash
cd server/apps/agent/skills/custom
rm -rf alerts allocation chat disposal liability report spending_leak time_machine
```

- [ ] **Step 4: 创建空的 custom 目录模板**

```bash
mkdir -p server/apps/agent/skills/custom
# 保留 family-asset-checkup 等额外技能作为参考（可选删除）
```

- [ ] **Step 5: 更新 DeerFlow 配置**

修改 `server/apps/agent/deerflow_config/base/config.yaml`:

```yaml
# 修改 skills.paths
skills:
  paths:
    - /app/apps/agent/skills/builtin
    # custom/{family_id} 路径由 family_adapter_cache 动态注入
```

- [ ] **Step 6: 验证目录结构**

```bash
ls -la server/apps/agent/skills/builtin/
ls -la server/apps/agent/skills/builtin/alerts/
```

Expected: 每个 builtin 子目录包含 SKILL.md 文件

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/skills/
git commit -m "refactor(agent): migrate skills to builtin directory structure"
```

---

## Task 2: 创建 skill_registry 数据库模型

**Files:**
- Create: `server/apps/backend/app/models/skill_registry.py`
- Modify: `server/apps/backend/app/models/__init__.py`

- [ ] **Step 1: 创建 SkillRegistry 模型文件**

创建 `server/apps/backend/app/models/skill_registry.py`:

```python
"""Skill registry model for per-family skill configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class SkillRegistry(Base):
    """Per-family skill configuration registry.

    Stores enabled status, display order, and metadata for both built-in
    and custom skills. Built-in skill metadata is synced from SKILL.md frontmatter;
    custom skill metadata is user-provided.
    """
    __tablename__ = "skill_registry"
    __table_args__ = (UniqueConstraint("family_id", "skill_id", name="uq_skill_registry_family_skill"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'fixed' | 'builtin' | 'custom'

    # UI metadata (only stored for custom skills; builtin synced from SKILL.md)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)  # emoji
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, default="trigger")
    placeholder: Mapped[str | None] = mapped_column(String(256), nullable=True)
    examples: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Configuration
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)  # for builtin prompt override

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

- [ ] **Step 2: 在 models/__init__.py 中导入新模型**

修改 `server/apps/backend/app/models/__init__.py`, 添加导入:

```python
from apps.backend.app.models.skill_registry import SkillRegistry
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/models/skill_registry.py server/apps/backend/app/models/__init__.py
git commit -m "feat(backend): add SkillRegistry model for per-family skill config"
```

---

## Task 3: 创建数据库迁移

**Files:**
- Create: `server/apps/backend/alembic/versions/xxx_add_skill_registry_table.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd server/apps/backend
uv run alembic revision --autogenerate -m "add skill_registry table"
```

- [ ] **Step 2: 检查生成的迁移文件**

检查生成的迁移文件是否包含:
- `skill_registry` 表创建
- `uq_skill_registry_family_skill` unique constraint
- `idx_skill_registry_family` index
- `idx_skill_registry_order` index

- [ ] **Step 3: 手动调整迁移文件（如需要）**

确保迁移文件包含正确的索引:

```python
# 在 upgrade() 中确认包含:
op.create_index('idx_skill_registry_family', 'skill_registry', ['family_id'])
op.create_index('idx_skill_registry_order', 'skill_registry', ['family_id', 'display_order'])
```

- [ ] **Step 4: 执行迁移**

```bash
cd server/apps/backend
uv run alembic upgrade head
```

- [ ] **Step 5: 验证表创建**

```bash
cd server/apps/backend
uv run python -c "from app.database import engine; from sqlalchemy import inspect; insp = inspect(engine); print(insp.get_table_names())"
```

Expected: `skill_registry` 在表列表中

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/alembic/versions/
git commit -m "feat(backend): add alembic migration for skill_registry table"
```

---

## Task 4: 扩展 workspace 服务支持自定义技能目录

**Files:**
- Modify: `server/apps/backend/app/services/workspace.py`

- [ ] **Step 1: 添加 skills_custom_dir 函数**

修改 `server/apps/backend/app/services/workspace.py`, 添加:

```python
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
        import shutil
        shutil.rmtree(skill_dir)
```

- [ ] **Step 2: Commit**

```bash
git add server/apps/backend/app/services/workspace.py
git commit -m "feat(backend): add custom skills directory helpers to workspace service"
```

---

## Task 5: 扩展 Backend ai_skills.py Router

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py`

- [ ] **Step 1: 扩展导入和常量**

修改 `server/apps/backend/app/routers/ai_skills.py`:

```python
"""技能配置管理路由（per-family）。支持内置技能配置和自定义技能 CRUD。"""

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
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

FIXED_CAPABILITIES = ["chat", "time_machine"]

BUILTIN_DEFAULT_ORDER = {
    "report": 100,
    "alerts": 101,
    "allocation": 102,
    "disposal": 103,
    "liability": 104,
    "spending_leak": 105,
}

# Skill ID validation pattern
SKILL_ID_PATTERN = re.compile(r^[a-z][a-z0-9_-]*$)
```

- [ ] **Step 2: 添加新的 Pydantic schemas**

```python
class SkillDefinition(BaseModel):
    """Skill definition returned to frontend."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_type: str  # 'fixed' | 'builtin' | 'custom'
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


class SkillListResponse(BaseModel):
    """Grouped skill list response."""
    fixed: list[SkillDefinition]
    builtin: list[SkillDefinition]
    custom: list[SkillDefinition]


class CustomSkillCreate(BaseModel):
    """Request body for creating a custom skill."""
    skill_id: str
    name: str
    description: str | None = None
    icon: str  # emoji
    color: str
    input_mode: str = "trigger"
    examples: list[str] | None = None
    prompt_content: str  # Markdown content for SKILL.md

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, v: str) -> str:
        if not SKILL_ID_PATTERN.match(v):
            raise ValueError("skill_id 只能包含小写字母、数字、下划线、连字符，且不能数字开头")
        if len(v) > 64:
            raise ValueError("skill_id 长度不能超过 64 字符")
        if v in BUILTIN_CAPABILITIES:
            raise ValueError("skill_id 不能与内置技能冲突")
        return v


class CustomSkillUpdate(BaseModel):
    """Request body for updating a custom skill."""
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    input_mode: str | None = None
    examples: list[str] | None = None
    prompt_content: str | None = None


class ReorderRequest(BaseModel):
    """Request body for batch reorder."""
    skill_ids: list[str]  # ordered list of skill_ids
```

- [ ] **Step 3: 实现新的 GET /ai/skills 端点**

```python
@router.get("", response_model=SkillListResponse)
def list_skills_grouped(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SkillListResponse:
    """列出所有技能，按 fixed/builtin/custom 分组，过滤禁用的技能。"""
    family_id = current_user.family_id

    # 查询家庭的 skill_registry 配置
    db_records = {
        r.skill_id: r
        for r in db.query(SkillRegistry)
        .filter(SkillRegistry.family_id == family_id)
        .all()
    }

    # Fixed capabilities (always shown, i18n handled by frontend)
    fixed = [
        SkillDefinition(
            id="chat",
            skill_type="fixed",
            display_order=0,
            is_enabled=True,
            can_edit=False,
            can_delete=False,
        ),
        SkillDefinition(
            id="time_machine",
            skill_type="fixed",
            display_order=1,
            is_enabled=True,
            can_edit=False,
            can_delete=False,
        ),
    ]

    # Builtin capabilities (filter is_enabled=false)
    builtin = []
    for skill_id in BUILTIN_CAPABILITIES:
        if skill_id in FIXED_CAPABILITIES:
            continue
        record = db_records.get(skill_id)
        is_enabled = record.is_enabled if record else True
        if not is_enabled:
            continue  # 过滤禁用的技能
        display_order = record.display_order if record else BUILTIN_DEFAULT_ORDER.get(skill_id, 100)
        builtin.append(
            SkillDefinition(
                id=skill_id,
                skill_type="builtin",
                display_order=display_order,
                is_enabled=is_enabled,
                can_edit=False,
                can_delete=False,
            )
        )

    # Custom skills (from skill_registry with skill_type='custom')
    custom = []
    for record in db.query(SkillRegistry).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_type == "custom",
    ).all():
        if not record.is_enabled:
            continue  # 过滤禁用的技能
        custom.append(
            SkillDefinition(
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

    # Sort by display_order
    builtin.sort(key=lambda s: s.display_order)
    custom.sort(key=lambda s: s.display_order)

    return SkillListResponse(fixed=fixed, builtin=builtin, custom=custom)
```

- [ ] **Step 4: 实现 POST /ai/skills 创建自定义技能**

```python
@router.post("", response_model=SkillDefinition)
def create_custom_skill(
    payload: CustomSkillCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinition:
    """创建自定义技能（仅 owner）。"""
    family_id = current_user.family_id

    # Check uniqueness
    existing = db.query(SkillRegistry).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_id == payload.skill_id,
    ).first()
    if existing:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"技能 ID '{payload.skill_id}' 已存在")

    # Determine display_order (max + 1 from existing custom skills)
    max_order = db.query(func.max(SkillRegistry.display_order)).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_type == "custom",
    ).scalar() or 199
    display_order = max_order + 1

    # Create SKILL.md file content
    skill_md_content = f"""---
name: {payload.name}
description: {payload.description or ''}
trigger_phrases:
  - {payload.name}
allowed-tools: []
thinking: false
---

{payload.prompt_content}
"""

    # Write to workspace
    workspace.create_custom_skill(str(family_id), payload.skill_id, skill_md_content)

    # Create database record
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

    return SkillDefinition(
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
```

- [ ] **Step 5: 实现 PUT /ai/skills/{skill_id} 更新自定义技能**

```python
@router.put("/{skill_id}", response_model=SkillDefinition)
def update_custom_skill(
    skill_id: str,
    payload: CustomSkillUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinition:
    """更新自定义技能（仅 owner）。"""
    family_id = current_user.family_id

    record = db.query(SkillRegistry).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_id == skill_id,
        SkillRegistry.skill_type == "custom",
    ).first()

    if not record:
        raise AppError(ErrorCode.NOT_FOUND, f"自定义技能 '{skill_id}' 不存在")

    # Update database fields
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

    # Update SKILL.md file if prompt_content provided
    if payload.prompt_content is not None:
        skill_md_content = f"""---
name: {record.name}
description: {record.description or ''}
trigger_phrases:
  - {record.name}
allowed-tools: []
thinking: false
---

{payload.prompt_content}
"""
        workspace.create_custom_skill(str(family_id), skill_id, skill_md_content)

    db.commit()
    db.refresh(record)

    return SkillDefinition(
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
```

- [ ] **Step 6: 实现 DELETE /ai/skills/{skill_id} 删除自定义技能**

```python
@router.delete("/{skill_id}")
def delete_custom_skill(
    skill_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """删除自定义技能（仅 owner）。"""
    family_id = current_user.family_id

    record = db.query(SkillRegistry).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_id == skill_id,
        SkillRegistry.skill_type == "custom",
    ).first()

    if not record:
        raise AppError(ErrorCode.NOT_FOUND, f"自定义技能 '{skill_id}' 不存在")

    # Delete database record
    db.delete(record)
    db.commit()

    # Delete SKILL.md file
    workspace.delete_custom_skill(str(family_id), skill_id)

    return {"ok": True}
```

- [ ] **Step 7: 实现 PUT /ai/skills/{skill_id}/toggle 启用/禁用**

```python
@router.put("/{skill_id}/toggle", response_model=SkillDefinition)
def toggle_skill(
    skill_id: str,
    payload: BaseModel,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> SkillDefinition:
    """启用/禁用技能（仅 owner，fixed 类型不可禁用）。"""

    class TogglePayload(BaseModel):
        is_enabled: bool

    payload = TogglePayload.model_validate(payload.__dict__)

    family_id = current_user.family_id

    if skill_id in FIXED_CAPABILITIES:
        raise AppError(ErrorCode.VALIDATION_ERROR, "固定能力不可禁用")

    # Find or create record
    record = db.query(SkillRegistry).filter(
        SkillRegistry.family_id == family_id,
        SkillRegistry.skill_id == skill_id,
    ).first()

    if not record:
        # Create new record for builtin skill
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

    skill_type = record.skill_type if record.skill_type else "builtin"
    return SkillDefinition(
        id=skill_id,
        skill_type=skill_type,
        display_order=record.display_order,
        is_enabled=record.is_enabled,
        can_edit=skill_type == "custom",
        can_delete=skill_type == "custom",
        name=record.name,
        description=record.description,
        icon=record.icon,
        color=record.color,
        input_mode=record.input_mode,
        examples=record.examples,
    )
```

- [ ] **Step 8: 实现 PUT /ai/skills/reorder 批量排序**

```python
@router.put("/reorder")
def reorder_skills(
    payload: ReorderRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """批量调整技能排序（仅 owner）。"""
    family_id = current_user.family_id

    for idx, skill_id in enumerate(payload.skill_ids):
        record = db.query(SkillRegistry).filter(
            SkillRegistry.family_id == family_id,
            SkillRegistry.skill_id == skill_id,
        ).first()

        if not record:
            # Create record for builtin skill if not exists
            if skill_id in BUILTIN_CAPABILITIES and skill_id not in FIXED_CAPABILITIES:
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
```

- [ ] **Step 9: 运行后端测试验证**

```bash
cd server/apps/backend
uv run pytest tests/ -v -k "skill"
```

Expected: 测试通过（如无现有测试则跳过）

- [ ] **Step 10: Commit**

```bash
git add server/apps/backend/app/routers/ai_skills.py
git commit -m "feat(backend): extend ai_skills router for custom skill CRUD and reorder"
```

---

## Task 6: 扩展 Agent CapabilityRegistry

**Files:**
- Modify: `server/apps/agent/services/capability_registry.py`

- [ ] **Step 1: 扩展导入和常量**

```python
"""Capability registry backed by DeerFlow skill definitions + family skill_registry."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
import yaml

from apps.agent.schemas.capability import (
    CapabilityDefinition,
    CapabilityPolicy,
    CapabilityUISchema,
)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
BUILTIN_DIR = SKILLS_DIR / "builtin"
CUSTOM_DIR = SKILLS_DIR / "custom"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

FIXED_CAPABILITIES = [
    CapabilityDefinition(
        id="chat",
        name="智能问答",
        description="回答关于净资产、资产配置、负债、趋势等问题",
        category="chat",
        ui=CapabilityUISchema(icon="message-circle", color="#06b6d4", route="/ai/chat", input_mode="free_text"),
        policy=CapabilityPolicy(allowed_roles=["member", "admin"], enable_thinking=True),
        skill_id="chat",
    ),
    CapabilityDefinition(
        id="time_machine",
        name="资产时光机",
        description="模拟 What-if 消费场景和财务推演",
        category="simulation",
        ui=CapabilityUISchema(icon="clock", color="#a855f7", route="/ai/time-machine", input_mode="free_text"),
        policy=CapabilityPolicy(allowed_roles=["member", "admin"], enable_thinking=True),
        skill_id="time_machine",
    ),
]

BUILTIN_DEFAULT_ORDER = {
    "report": 100,
    "alerts": 101,
    "allocation": 102,
    "disposal": 103,
    "liability": 104,
    "spending_leak": 105,
}
```

- [ ] **Step 2: 新增 list_capabilities_for_family 方法**

```python
class CapabilityRegistry:
    """Loads capabilities from builtin skills + family custom skills."""

    def __init__(self, backend_base_url: str | None = None, internal_token: str | None = None) -> None:
        self.skills_dir = SKILLS_DIR
        self._capabilities: dict[str, CapabilityDefinition] | None = None
        self._backend_base_url = backend_base_url
        self._internal_token = internal_token

    def list_capabilities_for_family(
        self,
        family_id: int,
        backend_base_url: str,
        internal_token: str,
    ) -> list[CapabilityDefinition]:
        """Merge and filter capabilities for a specific family."""
        # 1. Fetch family skill_registry from backend
        db_configs = self._fetch_skill_registry(family_id, backend_base_url, internal_token)
        db_map = {c["skill_id"]: c for c in db_configs}

        # 2. Fixed capabilities (always included)
        fixed = FIXED_CAPABILITIES.copy()

        # 3. Builtin capabilities (filter is_enabled=false)
        builtin = []
        for skill_dir in sorted(BUILTIN_DIR.glob("*")):
            if not skill_dir.is_dir():
                continue
            skill_id = skill_dir.name
            if skill_id in ("chat", "time_machine"):  # skip fixed
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            meta = self._read_frontmatter(skill_file)
            db_record = db_map.get(skill_id)

            # Filter disabled skills
            if db_record and not db_record.get("is_enabled", True):
                continue

            display_order = db_record.get("display_order") if db_record else BUILTIN_DEFAULT_ORDER.get(skill_id, 100)
            builtin.append(
                CapabilityDefinition(
                    id=skill_id,
                    name=str(meta.get("name") or skill_id),
                    description=str(meta.get("description") or ""),
                    category=str(meta.get("category") or "general"),
                    ui=CapabilityUISchema(
                        icon=str(meta.get("icon") or "message-circle"),
                        color=str(meta.get("color") or "#6366f1"),
                        route=f"/ai/{skill_id}",
                        input_mode=str(meta.get("input_mode") or "trigger"),
                    ),
                    policy=CapabilityPolicy(allowed_roles=["member", "admin"]),
                    skill_id=skill_id,
                    display_order=display_order,
                )
            )

        # 4. Custom capabilities from custom/{family_id}
        custom = []
        family_custom_dir = CUSTOM_DIR / str(family_id)
        if family_custom_dir.exists():
            for skill_dir in sorted(family_custom_dir.glob("*")):
                if not skill_dir.is_dir():
                    continue
                skill_id = skill_dir.name
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                db_record = db_map.get(skill_id)
                if db_record and not db_record.get("is_enabled", True):
                    continue

                meta = self._read_frontmatter(skill_file)
                display_order = db_record.get("display_order", 200) if db_record else 200

                custom.append(
                    CapabilityDefinition(
                        id=skill_id,
                        name=db_record.get("name") or str(meta.get("name") or skill_id),
                        description=db_record.get("description") or str(meta.get("description") or ""),
                        category="custom",
                        ui=CapabilityUISchema(
                            icon=db_record.get("icon") or "star",
                            color=db_record.get("color") or "#6366f1",
                            route=None,
                            input_mode=db_record.get("input_mode") or "trigger",
                        ),
                        policy=CapabilityPolicy(allowed_roles=["member", "admin"]),
                        skill_id=skill_id,
                        display_order=display_order,
                    )
                )

        # 5. Sort and return
        all_caps = fixed + builtin + custom
        all_caps.sort(key=lambda c: getattr(c, "display_order", 0))
        return all_caps

    def _fetch_skill_registry(
        self,
        family_id: int,
        backend_base_url: str,
        internal_token: str,
    ) -> list[dict]:
        """Fetch skill_registry records from backend."""
        try:
            url = f"{backend_base_url.rstrip('/')}/api/v1/internal/skill-registry/{family_id}"
            resp = httpx.get(url, headers={"X-Internal-Token": internal_token}, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.warning("Failed to fetch skill_registry for family %s", family_id)
            return []
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/services/capability_registry.py
git commit -m "feat(agent): extend CapabilityRegistry for family-level skill filtering"
```

---

## Task 7: 前端 API 扩展

**Files:**
- Modify: `frontend/apps/main/src/api/ai.ts`

- [ ] **Step 1: 添加新的 TypeScript 类型定义**

```typescript
// 在 ai.ts 中添加

export interface SkillDefinition {
  id: string
  skill_type: 'fixed' | 'builtin' | 'custom'
  name?: string
  description?: string
  icon?: string
  color?: string
  route?: string | null
  input_mode?: 'free_text' | 'trigger'
  examples?: string[]
  is_enabled: boolean
  display_order: number
  can_edit: boolean
  can_delete: boolean
}

export interface SkillListResponse {
  fixed: SkillDefinition[]
  builtin: SkillDefinition[]
  custom: SkillDefinition[]
}

export interface CustomSkillCreate {
  skill_id: string
  name: string
  description?: string
  icon: string
  color: string
  input_mode: 'trigger' | 'free_text'
  examples?: string[]
  prompt_content: string
}

export interface CustomSkillUpdate {
  name?: string
  description?: string
  icon?: string
  color?: string
  input_mode?: 'trigger' | 'free_text'
  examples?: string[]
  prompt_content?: string
}
```

- [ ] **Step 2: 添加新的 API 函数**

```typescript
// 获取分组技能列表
export const getSkillsGrouped = () =>
  http.get<SkillListResponse>('/ai/skills')

// 创建自定义技能
export const createCustomSkill = (payload: CustomSkillCreate) =>
  http.post<SkillDefinition>('/ai/skills', payload)

// 更新自定义技能
export const updateCustomSkill = (skillId: string, payload: CustomSkillUpdate) =>
  http.put<SkillDefinition>(`/ai/skills/${skillId}`, payload)

// 删除自定义技能
export const deleteCustomSkill = (skillId: string) =>
  http.delete<{ ok: boolean }>(`/ai/skills/${skillId}`)

// 启用/禁用技能
export const toggleSkill = (skillId: string, isEnabled: boolean) =>
  http.put<SkillDefinition>(`/ai/skills/${skillId}/toggle`, { is_enabled: isEnabled })

// 批量排序
export const reorderSkills = (skillIds: string[]) =>
  http.put<{ ok: boolean }>('/ai/skills/reorder', { skill_ids: skillIds })
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/api/ai.ts
git commit -m "feat(frontend): add skill management API types and functions"
```

---

## Task 8: 前端 i18n 配置

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 添加技能 i18n 配置到 zh-CN.ts**

在 `skills` section 中扩展:

```typescript
skills: {
  title: '技能管理',
  builtinSkills: '内置技能',
  customSkills: '自定义技能',
  fixedSkills: '固定能力',
  
  capability: {
    chat: {
      name: '💬 智能问答',
      description: '回答关于净资产、资产配置、负债、趋势等问题',
    },
    time_machine: {
      name: '⏰ 资产时光机',
      description: '模拟 What-if 消费场景和财务推演',
    },
    alerts: {
      name: '🔔 资产老化预警',
      description: '扫描即将到期或老化的资产，给出处置建议',
    },
    allocation: {
      name: '⚖️ 资产配置分析',
      description: '评估当前资产配置与目标配置的偏差，给出调整建议',
    },
    report: {
      name: '📊 家庭资产体检',
      description: '对家庭整体资产状况进行结构化分析',
    },
    disposal: {
      name: '🗑️ 闲置资产处置',
      description: '识别低效闲置资产，给出处置渠道和建议',
    },
    liability: {
      name: '💳 负债健康分析',
      description: '分析负债结构、还款压力和利率风险',
    },
    spending_leak: {
      name: '🔍 消费漏洞扫描',
      description: '识别低效消费和资产浪费，给出节省建议',
    },
  },
  
  // 自定义技能表单
  form: {
    skillId: '技能 ID',
    skillIdPlaceholder: '小写字母、数字、下划线、连字符',
    skillIdInvalid: 'ID 只能包含小写字母、数字、下划线、连字符，且不能数字开头',
    skillIdConflict: '该 ID 与内置技能冲突',
    skillIdExists: '该 ID 已存在',
    skillName: '技能名称',
    skillNamePlaceholder: '请输入技能名称',
    skillDescription: '描述',
    skillDescriptionPlaceholder: '可选，技能功能描述',
    skillIcon: '图标',
    skillColor: '颜色',
    skillInputMode: '输入模式',
    inputModeTrigger: '触发式',
    inputModeFreeText: '自由输入',
    skillExamples: '示例问题',
    skillExamplesPlaceholder: '触发此技能的示例问题',
    skillPrompt: '提示词内容',
    skillPromptPlaceholder: 'Markdown 格式的技能提示词',
    skillPromptTemplate: `## 任务描述
你是一个家庭资产分析助手...

## 输出格式
请以结构化格式输出分析结果...`,
    createBtn: '创建技能',
    updateBtn: '保存修改',
    deleteBtn: '删除',
    deleteConfirm: '⚠️ 确定要删除技能「{name}」吗？此操作不可撤销。',
    createSuccess: '✅ 技能创建成功',
    updateSuccess: '✅ 技能已更新',
    deleteSuccess: '🗑️ 技能已删除',
    reorderSuccess: '✅ 排序已保存',
  },
  
  // 技能详情查看
  detail: {
    viewPrompt: '查看提示词',
    hidePrompt: '收起提示词',
    promptLabel: '技能提示词',
  },
},
```

- [ ] **Step 2: 添加对应英文配置到 en-US.ts**

```typescript
skills: {
  title: 'Skill Management',
  builtinSkills: 'Built-in Skills',
  customSkills: 'Custom Skills',
  fixedSkills: 'Fixed Capabilities',
  
  capability: {
    chat: {
      name: '💬 AI Chat',
      description: 'Answer questions about net worth, allocation, liabilities, trends',
    },
    time_machine: {
      name: '⏰ Financial Simulator',
      description: 'What-if scenarios and financial projections',
    },
    alerts: {
      name: '🔔 Asset Aging Alerts',
      description: 'Scan assets nearing expiry or high maintenance',
    },
    allocation: {
      name: '⚖️ Allocation Analysis',
      description: 'Evaluate drift from target allocation',
    },
    report: {
      name: '📊 Financial Health Report',
      description: 'Comprehensive structured analysis',
    },
    disposal: {
      name: '🗑️ Idle Asset Disposal',
      description: 'Identify inefficient assets with disposal suggestions',
    },
    liability: {
      name: '💳 Liability Analysis',
      description: 'Analyze debt structure and pressure',
    },
    spending_leak: {
      name: '🔍 Spending Leak Detection',
      description: 'Identify wasteful spending patterns',
    },
  },
  
  form: {
    skillId: 'Skill ID',
    skillIdPlaceholder: 'lowercase letters, numbers, underscore, hyphen',
    skillIdInvalid: 'ID must contain only lowercase letters, numbers, underscore, hyphen, and cannot start with a number',
    skillIdConflict: 'This ID conflicts with a built-in skill',
    skillIdExists: 'This ID already exists',
    skillName: 'Skill Name',
    skillNamePlaceholder: 'Enter skill name',
    skillDescription: 'Description',
    skillDescriptionPlaceholder: 'Optional skill description',
    skillIcon: 'Icon',
    skillColor: 'Color',
    skillInputMode: 'Input Mode',
    inputModeTrigger: 'Trigger-based',
    inputModeFreeText: 'Free text',
    skillExamples: 'Example Questions',
    skillExamplesPlaceholder: 'Example triggers for this skill',
    skillPrompt: 'Prompt Content',
    skillPromptPlaceholder: 'Markdown skill prompt',
    skillPromptTemplate: `## Task Description
You are a family asset analysis assistant...

## Output Format
Output analysis in structured format...`,
    createBtn: 'Create Skill',
    updateBtn: 'Save Changes',
    deleteBtn: 'Delete',
    deleteConfirm: '⚠️ Delete skill "{name}"? This cannot be undone.',
    createSuccess: '✅ Skill created',
    updateSuccess: '✅ Skill updated',
    deleteSuccess: '🗑️ Skill deleted',
    reorderSuccess: '✅ Order saved',
  },
  
  detail: {
    viewPrompt: 'View Prompt',
    hidePrompt: 'Hide Prompt',
    promptLabel: 'Skill Prompt',
  },
},
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(frontend): add skill management i18n translations"
```

---

## Task 9: 改造 AIHubPage 三段展示

**Files:**
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`

- [ ] **Step 1: 更新 capabilities 计算属性**

```typescript
// 替换现有的 capabilities computed
const groupedSkills = ref<SkillListResponse | null>(null)
const loadingSkills = ref(false)

async function loadGroupedSkills() {
  loadingSkills.value = true
  try {
    const res = await getSkillsGrouped()
    groupedSkills.value = res.data
  } catch {
    // fallback to legacy capability store
    await capabilityStore.loadCapabilities()
  } finally {
    loadingSkills.value = false
  }
}

// 合并后的技能列表（用于模板渲染）
const allCapabilities = computed(() => {
  if (!groupedSkills.value) {
    return capabilityStore.capabilities
  }
  const { fixed, builtin, custom } = groupedSkills.value
  return [...fixed, ...builtin, ...custom]
})
```

- [ ] **Step 2: 更新技能卡片渲染逻辑**

```vue
<!-- 在 feature-grid 中更新渲染 -->
<div class="feature-grid" role="list">
  <button
    v-for="cap in allCapabilities"
    :key="cap.id"
    class="feature-card"
    role="listitem"
    :data-testid="`capability-${cap.id}`"
    :aria-label="getSkillLabel(cap)"
    @click="startCapability(cap)"
  >
    <span class="feature-icon" aria-hidden="true">{{ getSkillIcon(cap) }}</span>
    <!-- 内置技能使用 i18n -->
    <span v-if="cap.skill_type !== 'custom'" class="feature-title">
      {{ t(`skills.capability.${cap.id}.name`) }}
    </span>
    <span v-if="cap.skill_type !== 'custom'" class="feature-desc">
      {{ t(`skills.capability.${cap.id}.description`) }}
    </span>
    <!-- 自定义技能使用数据库值 -->
    <span v-else class="feature-title">{{ cap.name }}</span>
    <span v-else class="feature-desc">{{ cap.description }}</span>
  </button>
</div>
```

- [ ] **Step 3: 添加辅助函数**

```typescript
function getSkillIcon(cap: SkillDefinition) {
  if (cap.skill_type !== 'custom') {
    // 内置技能的 emoji 从 i18n name 中提取
    const nameKey = t(`skills.capability.${cap.id}.name`)
    const emojiMatch = nameKey.match(/^[\p{Emoji}]+/u)
    return emojiMatch ? emojiMatch[0] : '✨'
  }
  return cap.icon || '✨'
}

function getSkillLabel(cap: SkillDefinition) {
  if (cap.skill_type !== 'custom') {
    return `${t(`skills.capability.${cap.id}.name`)}：${t(`skills.capability.${cap.id}.description`)}`
  }
  return `${cap.name}：${cap.description || ''}`
}

function startCapability(cap: SkillDefinition) {
  if (cap.route) {
    router.push(cap.route)
  } else {
    // 自定义技能跳转到 chat 页面
    router.push('/ai/chat')
  }
}
```

- [ ] **Step 4: 更新 onMounted**

```typescript
onMounted(async () => {
  await aiStore.fetchConfig()
  if (aiStore.config?.ai_test_thinking_success === true) {
    deepThink.value = true
  }
  await loadGroupedSkills()
  await loadReport()
  startCapabilityPolling()
})
```

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue
git commit -m "feat(frontend): refactor AIHubPage for grouped skill display with i18n"
```

---

## Task 10: 改造 SkillsManagePage 支持自定义技能

**Files:**
- Modify: `frontend/apps/main/src/pages/SkillsManagePage.vue`

- [ ] **Step 1: 扩展导入和状态**

```typescript
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  getSkillsGrouped,
  createCustomSkill,
  updateCustomSkill,
  deleteCustomSkill,
  toggleSkill,
  reorderSkills,
  type SkillDefinition,
  type SkillListResponse,
  type CustomSkillCreate,
} from '@/api/ai'

const { t } = useI18n()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const groupedSkills = ref<SkillListResponse | null>(null)
const loading = ref(false)

// 新增/编辑表单状态
const showCreateForm = ref(false)
const showEditForm = ref(false)
const editingSkill = ref<SkillDefinition | null>(null)
const formDraft = ref<CustomSkillCreate>({
  skill_id: '',
  name: '',
  description: '',
  icon: '✨',
  color: '#6366f1',
  input_mode: 'trigger',
  examples: [],
  prompt_content: '',
})

// 表单校验状态
const skillIdError = ref('')
const checkingSkillId = ref(false)
```

- [ ] **Step 2: 添加技能 ID 即时校验**

```typescript
async function validateSkillId(value: string) {
  skillIdError.value = ''
  
  // 格式校验
  if (!/^[a-z][a-z0-9_-]*$/.test(value)) {
    skillIdError.value = t('skills.form.skillIdInvalid')
    return false
  }
  if (value.length > 64) {
    skillIdError.value = t('skills.form.skillIdInvalid')
    return false
  }
  
  // 内置冲突校验
  const builtinIds = ['alerts', 'allocation', 'chat', 'disposal', 'liability', 'report', 'spending_leak', 'time_machine']
  if (builtinIds.includes(value)) {
    skillIdError.value = t('skills.form.skillIdConflict')
    return false
  }
  
  // 家庭唯一性校验（检查 custom 列表）
  if (groupedSkills.value?.custom.some(s => s.id === value)) {
    skillIdError.value = t('skills.form.skillIdExists')
    return false
  }
  
  return true
}

// Watch skill_id changes for validation
watch(() => formDraft.value.skill_id, (val) => {
  if (val && showCreateForm.value) {
    validateSkillId(val)
  }
})
```

- [ ] **Step 3: 添加 CRUD 操作函数**

```typescript
async function loadSkills() {
  loading.value = true
  try {
    const res = await getSkillsGrouped()
    groupedSkills.value = res.data
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onToggle(skill: SkillDefinition, enabled: boolean) {
  if (!isOwner.value) return
  const prev = skill.is_enabled
  skill.is_enabled = enabled
  try {
    await toggleSkill(skill.id, enabled)
    showToast(enabled ? t('toast.enabled') : t('toast.disabled'))
    await loadSkills() // 重新加载以过滤禁用技能
  } catch {
    skill.is_enabled = prev
    showToast(t('toast.operationFailed'))
  }
}

function onCreateSkill() {
  formDraft.value = {
    skill_id: '',
    name: '',
    description: '',
    icon: '✨',
    color: '#6366f1',
    input_mode: 'trigger',
    examples: [],
    prompt_content: t('skills.form.skillPromptTemplate'),
  }
  skillIdError.value = ''
  showCreateForm.value = true
}

function onEditSkill(skill: SkillDefinition) {
  if (!isOwner.value || skill.skill_type !== 'custom') return
  editingSkill.value = skill
  formDraft.value = {
    skill_id: skill.id,
    name: skill.name || '',
    description: skill.description || '',
    icon: skill.icon || '✨',
    color: skill.color || '#6366f1',
    input_mode: (skill.input_mode as 'trigger' | 'free_text') || 'trigger',
    examples: skill.examples || [],
    prompt_content: '', // 需要单独获取
  }
  showEditForm.value = true
}

async function onSubmitCreate() {
  if (skillIdError.value) return
  if (!formDraft.value.skill_id || !formDraft.value.name || !formDraft.value.prompt_content) {
    showToast(t('common.failed'))
    return
  }
  
  try {
    await createCustomSkill(formDraft.value)
    showToast(t('skills.form.createSuccess'))
    showCreateForm.value = false
    await loadSkills()
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

async function onSubmitEdit() {
  if (!editingSkill.value) return
  
  try {
    await updateCustomSkill(editingSkill.value.id, {
      name: formDraft.value.name,
      description: formDraft.value.description,
      icon: formDraft.value.icon,
      color: formDraft.value.color,
      input_mode: formDraft.value.input_mode,
      examples: formDraft.value.examples,
      prompt_content: formDraft.value.prompt_content || undefined,
    })
    showToast(t('skills.form.updateSuccess'))
    showEditForm.value = false
    await loadSkills()
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

async function onDeleteSkill(skill: SkillDefinition) {
  if (!isOwner.value || skill.skill_type !== 'custom') return
  
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('skills.form.deleteConfirm', { name: skill.name || skill.id }),
    })
    await deleteCustomSkill(skill.id)
    showToast(t('skills.form.deleteSuccess'))
    await loadSkills()
  } catch {
    // cancelled or failed
  }
}
```

- [ ] **Step 4: 更新模板**

```vue
<template>
  <div class="skills-manage-page">
    <PageHeader :title="t('skills.title')" />

    <!-- Fixed capabilities -->
    <van-cell-group inset :title="t('skills.fixedSkills')" class="section">
      <van-cell
        v-for="skill in groupedSkills?.fixed ?? []"
        :key="skill.id"
        :title="t(`skills.capability.${skill.id}.name`)"
        :label="t(`skills.capability.${skill.id}.description`)"
        center
        is-link
        @click="onViewSkillDetail(skill)"
      />
    </van-cell-group>

    <!-- Builtin skills (with toggle) -->
    <van-cell-group inset :title="t('skills.builtinSkills')" class="section">
      <van-cell
        v-for="skill in groupedSkills?.builtin ?? []"
        :key="skill.id"
        :title="t(`skills.capability.${skill.id}.name`)"
        :label="t(`skills.capability.${skill.id}.description`)"
        center
        is-link
        @click="onViewSkillDetail(skill)"
      >
        <template #value>
          <van-switch
            :model-value="skill.is_enabled"
            size="20px"
            :disabled="!isOwner"
            @change="(v: boolean) => onToggle(skill, v)"
            @click.stop
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Custom skills -->
    <van-cell-group v-if="groupedSkills?.custom?.length" inset :title="t('skills.customSkills')" class="section">
      <van-cell
        v-for="skill in groupedSkills?.custom ?? []"
        :key="skill.id"
        :title="skill.name"
        :label="skill.description"
        center
      >
        <template #value>
          <div class="custom-skill-actions">
            <van-switch
              :model-value="skill.is_enabled"
              size="20px"
              :disabled="!isOwner"
              @change="(v: boolean) => onToggle(skill, v)"
              @click.stop
            />
            <van-icon v-if="isOwner" name="edit" size="18" @click.stop="onEditSkill(skill)" />
            <van-icon v-if="isOwner" name="delete-o" size="18" @click.stop="onDeleteSkill(skill)" />
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Add skill button -->
    <div v-if="isOwner" class="add-skill-btn">
      <van-button block type="primary" @click="onCreateSkill">
        {{ t('skills.form.createBtn') }}
      </van-button>
    </div>

    <!-- Create/Edit form popup -->
    <van-popup
      v-model:show="showCreateForm || showEditForm"
      position="bottom"
      round
      :style="{ height: '90%', display: 'flex', flexDirection: 'column' }"
    >
      <!-- Form content here -->
    </van-popup>
  </div>
</template>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/SkillsManagePage.vue
git commit -m "feat(frontend): extend SkillsManagePage for custom skill CRUD"
```

---

## Task 11: 集成测试与验收

**Files:**
- Test: `server/apps/backend/tests/test_skill_registry.py`
- Test: `frontend/apps/main/src/__tests__/skillValidation.test.ts`

- [ ] **Step 1: 创建后端单元测试**

创建 `server/apps/backend/tests/test_skill_registry.py`:

```python
"""Unit tests for skill_registry model and router."""

import pytest
from apps.backend.app.models.skill_registry import SkillRegistry


def test_skill_registry_model_defaults():
    """Test default values for SkillRegistry model."""
    record = SkillRegistry(
        family_id=1,
        skill_id="my_skill",
        skill_type="custom",
    )
    assert record.is_enabled is True
    assert record.display_order == 0


def test_skill_id_validation_valid():
    """Test valid skill_id patterns."""
    valid_ids = ["my_skill", "skill123", "a-b_c", "lowercaseonly"]
    from apps.backend.app.routers.ai_skills import SKILL_ID_PATTERN
    for skill_id in valid_ids:
        assert SKILL_ID_PATTERN.match(skill_id)


def test_skill_id_validation_invalid():
    """Test invalid skill_id patterns."""
    invalid_ids = ["123skill", "Skill", "skill id", "skill!"]
    from apps.backend.app.routers.ai_skills import SKILL_ID_PATTERN
    for skill_id in invalid_ids:
        assert not SKILL_ID_PATTERN.match(skill_id)
```

- [ ] **Step 2: 运行后端测试**

```bash
cd server/apps/backend
uv run pytest tests/test_skill_registry.py -v
```

Expected: 测试通过

- [ ] **Step 3: 运行前端类型检查**

```bash
cd frontend/apps/main
npm run typecheck
```

Expected: 无类型错误

- [ ] **Step 4: Commit 测试文件**

```bash
git add server/apps/backend/tests/test_skill_registry.py
git commit -m "test(backend): add skill_registry unit tests"
```

---

## Spec Coverage Check

| Spec Section | Covered Task |
|--------------|--------------|
| 目录结构迁移 | Task 1 |
| skill_registry 数据库表 | Task 2, Task 3 |
| workspace 服务扩展 | Task 4 |
| Backend API CRUD | Task 5 |
| CapabilityRegistry 扩展 | Task 6 |
| 前端 API 类型 | Task 7 |
| i18n 配置 | Task 8 |
| AIHubPage 改造 | Task 9 |
| SkillsManagePage 改造 | Task 10 |
| 测试验收 | Task 11 |

---

Plan complete and saved to `docs/superpowers/plans/2026-05-20-ai-skill-management.md`. 

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**