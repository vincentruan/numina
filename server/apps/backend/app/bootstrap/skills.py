"""Bootstrap builtin skills (system-wide templates, family_id=0)."""

from sqlalchemy.orm import Session

from apps.backend.app.constants.system_ids import (
    SKILL_REPORT_ID,
)
from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

_BUILTIN_SKILLS = [
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
