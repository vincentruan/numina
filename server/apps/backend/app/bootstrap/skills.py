"""Bootstrap builtin skills (system-wide templates, family_id=0)."""

from sqlalchemy.orm import Session

from apps.backend.app.constants.system_ids import (
    SKILL_FAMILY_ASSET_CHECKUP_ID,
    SKILL_FAMILY_FINANCE_INSIGHT_PLANNER_ID,
    SKILL_FAMILY_LIABILITY_REVIEW_ID,
    SKILL_FIXED_ASSET_FOLLOWUP_ID,
    SKILL_REPORT_ID,
)
from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

_BUILTIN_SKILLS = [
    {
        "id": SKILL_FAMILY_ASSET_CHECKUP_ID,
        "skill_id": "family-asset-checkup",
        "name": "家庭资产体检",
        "description": "家庭资产体检分析。综合评估家庭资产健康度，输出评分卡、风险标记和建议。",
        "icon": "🏥",
        "color": "#10B981",
        "input_mode": "trigger",
        "display_order": 10,
    },
    {
        "id": SKILL_REPORT_ID,
        "skill_id": "report",
        "name": "资产健康报告",
        "description": "家庭资产健康报告。综合分析家庭财务状况，输出评分、风险标记和建议。",
        "icon": "📊",
        "color": "#10B981",
        "input_mode": "trigger",
        "display_order": 5,
    },
    {
        "id": SKILL_FAMILY_FINANCE_INSIGHT_PLANNER_ID,
        "skill_id": "family-finance-insight-planner",
        "name": "财务深度研究",
        "description": "家庭财务深度研究规划器。处理需要多步骤推理的复杂财务问题，启用规划模式。",
        "icon": "🔬",
        "color": "#6366F1",
        "input_mode": "trigger",
        "display_order": 20,
    },
    {
        "id": SKILL_FAMILY_LIABILITY_REVIEW_ID,
        "skill_id": "family-liability-review",
        "name": "负债结构分析",
        "description": "家庭负债结构分析。评估还款压力、利率风险和期限结构。",
        "icon": "💳",
        "color": "#F59E0B",
        "input_mode": "trigger",
        "display_order": 30,
    },
    {
        "id": SKILL_FIXED_ASSET_FOLLOWUP_ID,
        "skill_id": "fixed-asset-followup",
        "name": "固定资产跟踪",
        "description": "固定资产跟踪与老化预警。识别老化风险、维护需求和闲置成本。",
        "icon": "🏠",
        "color": "#8B5CF6",
        "input_mode": "trigger",
        "display_order": 40,
    },
]


def bootstrap_skills(db: Session) -> None:
    """Ensure builtin skills exist as system-wide templates. Idempotent."""
    from apps.backend.app.models.skill_registry import SkillRegistry

    inserted = 0
    for skill_data in _BUILTIN_SKILLS:
        existing = db.query(SkillRegistry).filter(
            SkillRegistry.family_id == 0,
            SkillRegistry.skill_id == skill_data["skill_id"],
        ).first()

        if existing:
            continue

        skill = SkillRegistry(
            id=skill_data["id"],
            family_id=0,
            skill_id=skill_data["skill_id"],
            skill_type="builtin",
            name=skill_data["name"],
            description=skill_data["description"],
            icon=skill_data["icon"],
            color=skill_data["color"],
            input_mode=skill_data["input_mode"],
            display_order=skill_data["display_order"],
            is_enabled=True,
            creation_type="manual",
        )
        db.add(skill)
        inserted += 1

    if inserted:
        db.commit()
        logger.info(f"已初始化 {inserted} 个内置技能模板")
