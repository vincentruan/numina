"""定时任务相关的 Pydantic schemas。

字段格式校验（技能白名单、cron 有效性）在路由层用 ``AppError`` 完成，
以便返回 400 而不是 Pydantic 的 422。
"""

from datetime import datetime

from pydantic import Field

from apps.backend.app.schemas.base import SnowflakeBase

# 当前支持定时调度的技能白名单。扩展前需确认对应技能可无人值守执行。
# 标识符必须与 agent gateway 路由及 ai_skills.RESERVED_NAMES 中的 skill_id 一致。
ALLOWED_SCHEDULABLE_SKILLS: frozenset[str] = frozenset(
    {"asset-report", "literacy-weekly-report"}
)


class ScheduledTaskCreate(SnowflakeBase):
    skill_id: str = Field(max_length=50)
    cron_expression: str = Field(max_length=100)
    is_enabled: bool = True


class ScheduledTaskUpdate(SnowflakeBase):
    skill_id: str | None = Field(default=None, max_length=50)
    cron_expression: str | None = Field(default=None, max_length=100)
    is_enabled: bool | None = None


class ScheduledTaskResponse(SnowflakeBase):
    id: int
    family_id: int
    skill_id: str
    cron_expression: str
    is_enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None = None
    status: str
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduledTaskListResponse(SnowflakeBase):
    items: list[ScheduledTaskResponse] = []
