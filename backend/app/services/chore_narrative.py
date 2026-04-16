"""AI narrative generation for chore approvals.

Calls the agent service with a 2-second timeout.
Falls back to a fixed template on timeout or any error.
Skips AI entirely if family.ai_enabled is False.
"""

import logging

import httpx

from app.config import settings
from app.models.family import Family

logger = logging.getLogger(__name__)


def _fallback_narrative(chore_name: str, coins: int) -> tuple[str, str]:
    return f"你完成了{chore_name}！获得 {coins} 颗星", "⭐"


async def generate_narrative(
    family: Family,
    child_name: str,
    chore_name: str,
    coins: int,
    streak: int,
) -> tuple[str, str]:
    """Return (narrative_text, emoji). Never raises — falls back to fixed template."""
    if not family.ai_enabled:
        return _fallback_narrative(chore_name, coins)

    prompt = (
        f"请用不超过30个中文字，为一个叫{child_name}的小朋友写一句鼓励的话。"
        f"他/她刚完成了家务：{chore_name}，获得了{coins}颗星星币。"
        f"{'连续完成了' + str(streak) + '天，' if streak > 1 else ''}"
        f"请在句子前加1-3个相关表情符号，格式：表情 文字。只输出这一句话，不要其他内容。"
    )

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/chat/ask",
                json={"question": prompt},
                headers={"X-Internal-Token": settings.AGENT_INTERNAL_TOKEN},
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
