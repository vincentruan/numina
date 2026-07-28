"""AI batch generation utility for expanding the scenario template library.

Provides two entry points:

* ``seed_templates(db)`` — inserts the 12 hand-crafted seed templates (4 dimensions
  x 3 age groups) if they don't already exist. Idempotent; safe to call on every
  startup or from a migration.

* ``generate_templates_batch(db, family_id, user_id)`` — finds dimension x age_group
  combinations with fewer than 3 active templates, asks the lightweight LLM (via
  ``AgentClient``) to generate one template per gap, validates the response, and
  returns the list of generated dicts (caller decides whether to persist).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.literacy_scenario import LiteracyScenarioTemplate

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_DIMENSIONS = ["earning", "choosing", "waiting", "caring"]
VALID_AGE_GROUPS = ["low", "mid", "high"]
MIN_TEMPLATES_PER_SLOT = 3

# ── Seed data ──────────────────────────────────────────────────────────────────
# Identical to the TEMPLATE_SEEDS in the migration (l1t2e3r4a5c6). Kept here so
# the application can re-seed without relying on migration replay.

_SEED_TEMPLATES: list[dict[str, Any]] = [
    # earning — low
    {
        "dimension": "earning",
        "age_group": "low",
        "story_template": "小明今天帮妈妈做了一件事，得到了一些星币⭐。你觉得小明做了什么？",
        "choices": [
            {"text": "帮妈妈扫地 🧹", "feedback": "扫地是让家里变干净的劳动，值得奖励！", "dimension_signal": "earning"},
            {"text": "整理自己的玩具 🧸", "feedback": "整理好自己的东西也是一种负责任的表现！", "dimension_signal": "earning"},
            {"text": "帮妈妈拿东西 🛍️", "feedback": "帮助家人是一种很好的赚钱方式！", "dimension_signal": "earning"},
        ],
    },
    # earning — mid
    {
        "dimension": "earning",
        "age_group": "mid",
        "story_template": "这周你有机会通过额外的努力赚取星币。你会选择？",
        "choices": [
            {"text": "每天多做1个简单任务（5天×2⭐=10⭐）", "feedback": "稳定的小努力可以积累成不小的收获！", "dimension_signal": "earning"},
            {"text": "周末做一个大任务（一次赚8⭐）", "feedback": "集中时间做大事效率很高，但别忘了持续性也很重要。", "dimension_signal": "earning"},
            {"text": "这周先休息，下周再赚", "feedback": "偶尔休息没问题，但延迟开始也会延迟目标的达成哦。", "dimension_signal": "earning"},
        ],
    },
    # earning — high
    {
        "dimension": "earning",
        "age_group": "high",
        "story_template": (
            "你有两个周末可以赚取星币：帮邻居整理花园(100⭐,3小时) "
            "或教弟弟妹妹做题(60⭐,1小时)。但你还想攒钱买一个200⭐的东西。"
        ),
        "choices": [
            {"text": "两个周末都整理花园(200⭐,6小时)", "feedback": "最大化收入！虽然辛苦但能最快达成目标。", "dimension_signal": "earning"},
            {"text": "两个周末都教题(120⭐,2小时)", "feedback": "轻松一些，但需要更多周才能攒够200⭐。", "dimension_signal": "earning"},
            {"text": "第一个周末整理花园，第二个教题(160⭐,4小时)", "feedback": "平衡策略：先快速接近目标，再轻松一些。", "dimension_signal": "earning"},
        ],
    },
    # choosing — low
    {
        "dimension": "choosing",
        "age_group": "low",
        "story_template": "小熊有5颗星币，它看到🍎苹果玩具(3星币)和🧸小熊玩偶(5星币)。它只能买一个！",
        "choices": [
            {"text": "买🍎苹果玩具(3⭐)，还剩2⭐", "feedback": "买了便宜的还能存下一些，不过小熊玩偶就买不了啦。", "dimension_signal": "choosing"},
            {"text": "买🧸小熊玩偶(5⭐)，星币用完", "feedback": "得到了最喜欢的，但星币就花光啦！", "dimension_signal": "choosing"},
            {"text": "都不买，继续攒星币", "feedback": "耐心等待可以买到更好的东西哦！", "dimension_signal": "choosing"},
        ],
    },
    # choosing — mid
    {
        "dimension": "choosing",
        "age_group": "mid",
        "story_template": "你有30颗星币，可以现在买一个小玩具(15⭐)，或者再等两周(每周赚10⭐)买一个大玩具(40⭐)。",
        "choices": [
            {"text": "现在买小玩具(15⭐)，剩15⭐", "feedback": "马上得到了满足，但大玩具就还要再等更久了。", "dimension_signal": "choosing"},
            {"text": "等两周买大玩具(40⭐)", "feedback": "延迟满足需要耐心，但最终获得的东西更值得！", "dimension_signal": "choosing"},
            {"text": "先买小玩具，两周后再说", "feedback": "注意：小玩具花了15⭐，两周后只有20⭐+15⭐=35⭐，还不够大玩具呢。", "dimension_signal": "choosing"},
        ],
    },
    # choosing — high
    {
        "dimension": "choosing",
        "age_group": "high",
        "story_template": (
            "你有50颗星币。现在有一个限时打折的文具套装(35⭐)，但你已经攒了3周"
            "准备买一个80⭐的拼图。如果现在买文具，拼图还要再攒多久？（每周赚15⭐）"
        ),
        "choices": [
            {"text": "买文具套装(35⭐)，剩15⭐", "feedback": "文具买了还剩15⭐，拼图还需(80-15)/15≈5周。机会成本：额外多等了约2周。", "dimension_signal": "choosing"},
            {"text": "不买文具，继续攒拼图", "feedback": "再攒2周就够80⭐了！忍住诱惑是延迟满足的关键。", "dimension_signal": "choosing"},
            {"text": "再想想，文具是不是真的需要", "feedback": "好问题！买东西前问自己「我真的需要吗？」可以避免冲动消费。", "dimension_signal": "choosing"},
        ],
    },
    # waiting — low
    {
        "dimension": "waiting",
        "age_group": "low",
        "story_template": "小兔子有3颗星币，它想要一个大蛋糕🎂(8星币)。它应该怎么办？",
        "choices": [
            {"text": "每天帮妈妈做事赚1⭐，等5天", "feedback": "耐心等待5天就能吃到大蛋糕啦！🎉", "dimension_signal": "waiting"},
            {"text": "先买个小饼干(3⭐)解馋", "feedback": "小饼干可以吃，但大蛋糕就还要等更久哦。", "dimension_signal": "waiting"},
            {"text": "找好朋友一起攒，更快！", "feedback": "和朋友一起努力可以让目标更快实现！", "dimension_signal": "waiting"},
        ],
    },
    # waiting — mid
    {
        "dimension": "waiting",
        "age_group": "mid",
        "story_template": "你看到一个你喜欢的东西(20⭐)，你现在有15⭐。每天做2个任务可以赚4⭐。",
        "choices": [
            {"text": "再做2天任务就够了(还需5⭐≈2天)", "feedback": "只差2天了！坚持一下就能买到，延迟满足的感觉很棒。", "dimension_signal": "waiting"},
            {"text": "现在找家人借5⭐", "feedback": "借了就要还，意味着未来几天要做额外任务。有时候等待比借更好。", "dimension_signal": "waiting"},
            {"text": "放弃这个，换一个更便宜的(15⭐)", "feedback": "降低目标也是一种选择，但想想你是不是真的更喜欢原来那个。", "dimension_signal": "waiting"},
        ],
    },
    # waiting — high
    {
        "dimension": "waiting",
        "age_group": "high",
        "story_template": (
            "你有60⭐。一个限时商品45⭐今天截止，但你正在攒150⭐买一个你真正想要的东西。"
            "如果你买了限时商品，你之前6周的积累就白费了吗？（每周赚15⭐）"
        ),
        "choices": [
            {"text": "买限时商品(45⭐)，剩15⭐", "feedback": "之前6周攒了60⭐不算白费，但还需(150-15)/15=9周！从原来6周变成9周了。", "dimension_signal": "waiting"},
            {"text": "忍住不买，继续攒150⭐目标", "feedback": "限时感往往是冲动的陷阱。真正想要的东西值得等待，目标只差6周了！", "dimension_signal": "waiting"},
            {"text": "买限时商品，但下周开始多做一个任务", "feedback": "积极弥补！如果每周多赚5⭐，需要(150-15)/20≈7周，比不弥补好一些。", "dimension_signal": "waiting"},
        ],
    },
    # caring — low
    {
        "dimension": "caring",
        "age_group": "low",
        "story_template": "姐姐只有2颗星币，但她很想要一个贴纸🌟(5⭐)。你有10颗星币，你会？",
        "choices": [
            {"text": "给姐姐3⭐，帮她买贴纸", "feedback": "分享让姐姐开心，你还有7⭐，真棒！❤️", "dimension_signal": "caring"},
            {"text": "教姐姐怎么赚星币", "feedback": "授人以鱼不如授人以渔！教姐姐赚钱的方法更好。", "dimension_signal": "caring"},
            {"text": "自己的星币自己留着", "feedback": "保护好自己的星币也没错，但下次可以想想怎么帮助家人。", "dimension_signal": "caring"},
        ],
    },
    # caring — mid
    {
        "dimension": "caring",
        "age_group": "mid",
        "story_template": "家里需要买一个新的日历📅(15⭐)，但如果你贡献10⭐，你自己的攒钱计划就会慢下来。",
        "choices": [
            {"text": "贡献10⭐买日历", "feedback": "家庭用品大家一起承担是好的！你的计划只是慢一点，并没有失败。", "dimension_signal": "caring"},
            {"text": "贡献5⭐，让其他人也出一些", "feedback": "合理的分担方式！每个人出一部分，公平又不会太影响自己。", "dimension_signal": "caring"},
            {"text": "这次不贡献，下次再说", "feedback": "偶尔不贡献没问题，但家庭共同责任需要大家一起承担。", "dimension_signal": "caring"},
        ],
    },
    # caring — high
    {
        "dimension": "caring",
        "age_group": "high",
        "story_template": (
            "家庭有一个共同目标：攒500⭐全家去旅行。你现在有80⭐。"
            "如果全家每周需要每人贡献20⭐，你愿意把你攒了4周的星币投入家庭目标吗？"
        ),
        "choices": [
            {"text": "愿意！全家旅行比个人目标更有意义", "feedback": "家庭目标需要每个人的贡献。你的80⭐足够4周的贡献，旅行回忆是无价的。", "dimension_signal": "caring"},
            {"text": "愿意，但希望每周只贡献10⭐", "feedback": "坦诚沟通你的想法很好！和家人商量一个你能承受的额度。", "dimension_signal": "caring"},
            {"text": "想先保留，看看个人目标能不能兼顾", "feedback": "合理考虑。但500⭐÷全家人数=每人约125-165⭐，你的80⭐是重要的一部分。", "dimension_signal": "caring"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Public: seed_templates
# ---------------------------------------------------------------------------

def seed_templates(db: Session) -> int:
    """Insert the 12 hand-crafted seed templates if they don't exist.

    Idempotent: each (dimension, age_group) combination is checked before
    insertion, so calling this multiple times never creates duplicates.

    Returns the number of templates inserted.
    """
    inserted = 0
    for tmpl in _SEED_TEMPLATES:
        exists = db.execute(
            select(LiteracyScenarioTemplate.id).where(
                LiteracyScenarioTemplate.dimension == tmpl["dimension"],
                LiteracyScenarioTemplate.age_group == tmpl["age_group"],
            )
        ).first()
        if exists is not None:
            continue

        row = LiteracyScenarioTemplate(
            dimension=tmpl["dimension"],
            age_group=tmpl["age_group"],
            story_template=tmpl["story_template"],
            choices_json=json.dumps(tmpl["choices"], ensure_ascii=False),
            is_active=True,
        )
        db.add(row)
        inserted += 1

    if inserted:
        db.commit()
    return inserted


# ---------------------------------------------------------------------------
# Public: generate_templates_batch
# ---------------------------------------------------------------------------

def _find_gaps(db: Session) -> list[tuple[str, str]]:
    """Return (dimension, age_group) pairs with fewer than ``MIN_TEMPLATES_PER_SLOT`` active templates."""
    gaps: list[tuple[str, str]] = []
    for dim in VALID_DIMENSIONS:
        for age in VALID_AGE_GROUPS:
            count = db.execute(
                select(LiteracyScenarioTemplate.id).where(
                    LiteracyScenarioTemplate.dimension == dim,
                    LiteracyScenarioTemplate.age_group == age,
                    LiteracyScenarioTemplate.is_active.is_(True),
                )
            ).all()
            if len(count) < MIN_TEMPLATES_PER_SLOT:
                gaps.append((dim, age))
    return gaps


def _build_generation_prompt(dimension: str, age_group: str) -> str:
    """Build a prompt asking the LLM to generate a scenario template."""
    age_descriptions = {
        "low": "5-7岁，简单、多emoji、短句",
        "mid": "8-10岁，有具体情境、贴近生活",
        "high": "11岁以上，有具体数字、权衡取舍、复杂场景",
    }
    dimension_descriptions = {
        "earning": "赚钱——通过劳动或努力获得星币",
        "choosing": "选择——在有限资源下做决策，理解机会成本",
        "waiting": "等待——延迟满足，为目标而储蓄",
        "caring": "关心——分享、家庭责任、帮助他人",
    }
    return (
        "你是一位儿童财商启蒙专家。请为以下维度和年龄段生成一个情境模板。\n\n"
        f"维度：{dimension}（{dimension_descriptions.get(dimension, '')}）\n"
        f"年龄段：{age_group}（{age_descriptions.get(age_group, '')}）\n\n"
        "要求：\n"
        "1. story_template: 一个简短的情境故事（中文），适合该年龄段\n"
        "2. choices: 2-4个选择项，每项包含 text（选择文字）、feedback（反馈）、dimension_signal（维度信号，固定为"
        f'"{dimension}"）\n\n'
        '请用 JSON 输出，格式：{"story_template": "...", "choices": [{"text": "...", "feedback": "...", '
        '"dimension_signal": "..."}]}。\n'
        "只输出 JSON，不要附加解释。"
    )


def _validate_generated_template(data: dict[str, Any], dimension: str) -> bool:
    """Validate the structure of an LLM-generated template."""
    if not isinstance(data, dict):
        return False
    story = data.get("story_template")
    if not story or not isinstance(story, str):
        return False
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) < 2 or len(choices) > 4:
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            return False
        if not choice.get("text") or not choice.get("feedback"):
            return False
        # dimension_signal must match the target dimension
        if choice.get("dimension_signal") != dimension:
            return False
    return True


async def generate_templates_batch(
    db: Session,
    family_id: int,
    user_id: int,
) -> list[dict[str, Any]]:
    """Generate scenario templates for dimension x age_group slots that need more variety.

    For each slot with fewer than ``MIN_TEMPLATES_PER_SLOT`` active templates, calls
    the lightweight LLM via ``AgentClient`` to generate one template. Returns a list
    of generated template dicts (not yet persisted — caller decides).

    Each returned dict has keys: ``dimension``, ``age_group``, ``story_template``,
    ``choices_json`` (JSON string).
    """
    gaps = _find_gaps(db)
    if not gaps:
        logger.info("generate_templates_batch: all slots have >= %d templates, nothing to do", MIN_TEMPLATES_PER_SLOT)
        return []

    try:
        from apps.backend.app.services.agent_client import (
            AgentClient,  # deferred import
        )
    except Exception:  # pragma: no cover - import-time failure
        logger.exception("generate_templates_batch: failed to import AgentClient")
        return []

    generated: list[dict[str, Any]] = []

    for dimension, age_group in gaps:
        prompt = _build_generation_prompt(dimension, age_group)
        body = {"prompt": prompt, "max_tokens": 512, "temperature": 0.7}
        client = AgentClient(family_id=family_id, user_id=user_id, timeout=45.0)

        try:
            resp = await client.post("/suggest/asset", json=body)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            logger.warning(
                "generate_templates_batch: LLM call failed for %s/%s, skipping",
                dimension, age_group, exc_info=True,
            )
            continue

        data = payload.get("data") or payload
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("generate_templates_batch: LLM returned non-JSON for %s/%s", dimension, age_group)
                continue

        if not _validate_generated_template(data, dimension):
            logger.warning("generate_templates_batch: invalid template structure for %s/%s", dimension, age_group)
            continue

        choices_json = json.dumps(data["choices"], ensure_ascii=False)
        generated.append({
            "dimension": dimension,
            "age_group": age_group,
            "story_template": data["story_template"],
            "choices_json": choices_json,
        })

    return generated
