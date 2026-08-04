"""AI narrative generation for chore approvals.

Calls the agent service with a 2-second timeout.
Falls back to a fixed template on timeout or any error.
Skips AI entirely if the family has no active AIProviderConfig.
"""

import logging

from apps.backend.app.models.family import Family
from apps.backend.app.services.agent_client import AgentClient

logger = logging.getLogger(__name__)


def _fallback_narrative(chore_name: str, coins: int, multiplier: float = 1.0) -> tuple[str, str]:
    if multiplier >= 2.0:
        return f"你完成了{chore_name}！连续打卡双倍奖励，获得 {coins} 颗星 🔥🔥", "🔥"
    if multiplier >= 1.5:
        return f"你完成了{chore_name}！连续打卡加成，获得 {coins} 颗星 🔥", "🔥"
    return f"你完成了{chore_name}！获得 {coins} 颗星", "⭐"


def _is_ai_enabled(family: Family) -> bool:
    """Check if the family has AI enabled (family-level toggle)."""
    return bool(family.ai_enabled)


async def generate_narrative(
    family: Family,
    child_name: str,
    chore_name: str,
    coins: int,
    streak: int,
    multiplier: float = 1.0,
) -> tuple[str, str]:
    """Return (narrative_text, emoji). Never raises — falls back to fixed template."""
    if not _is_ai_enabled(family):
        return _fallback_narrative(chore_name, coins, multiplier)

    bonus_hint = ""
    if multiplier >= 2.0:
        bonus_hint = "今天是双倍奖励日！"
    elif multiplier >= 1.5:
        bonus_hint = "今天是1.5倍奖励日！"

    prompt = (
        f"请用不超过30个中文字，为一个叫{child_name}的小朋友写一句鼓励的话。"
        f"他/她刚完成了家务：{chore_name}，获得了{coins}颗星星币。"
        f"{'连续完成了' + str(streak) + '天，' if streak > 1 else ''}"
        f"{bonus_hint}"
        f"请在句子前加1-3个相关表情符号，格式：表情 文字。只输出这一句话，不要其他内容。"
    )

    try:
        agent_client = AgentClient(family_id="system", timeout=2.0)
        resp = await agent_client.post(
            "/chat/ask",
            json={"question": prompt},
        )
        resp.raise_for_status()
        answer: str = resp.json().get("answer", "").strip()
        if not answer:
            return _fallback_narrative(chore_name, coins)
        # Split leading emoji from text
        parts = answer.split(" ", 1)
        if len(parts) == 2:
            return parts[1], parts[0]
        return answer, "⭐"
    except Exception:
        logger.debug("AI narrative generation failed, using fallback", exc_info=True)
        return _fallback_narrative(chore_name, coins)
