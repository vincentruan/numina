"""Content safety filter for AI tutor output — rule-based keyword/pattern filtering."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocked keyword/pattern lists (Chinese + English)
# Organized by category for logging granularity.
# ---------------------------------------------------------------------------

_VIOLENCE_PATTERNS = [
    re.compile(r"杀[死害]?|砍[死伤]?|枪[击杀]|爆[炸击]|自[杀杀]|虐待"),
    re.compile(r"kill|murder|shoot|bomb|suicide|torture|massacre", re.IGNORECASE),
]

_HORROR_PATTERNS = [
    re.compile(r"鬼[魂故事]|恐怖[事件袭]|血腥|僵尸|丧尸|恶[魔鬼]"),
    re.compile(r"ghost|horror|bloody|zombie|demon|nightmare", re.IGNORECASE),
]

_INAPPROPRIATE_PATTERNS = [
    re.compile(r"色情|裸[体露]|性[交爱]|吸毒|贩毒|赌博|赌[博钱]"),
    re.compile(r"porn|naked|sex(?:ual)?|drug(?:s)?|gambling", re.IGNORECASE),
]

_NON_EDUCATIONAL_PATTERNS = [
    re.compile(r"政[治府]|宗教|迷[信教]|邪教|传销"),
    re.compile(r"politics|religion|cult|extremism", re.IGNORECASE),
]

# Category label → patterns
RULE_CATEGORIES: dict[str, list[re.Pattern]] = {
    "violence": _VIOLENCE_PATTERNS,
    "horror": _HORROR_PATTERNS,
    "inappropriate": _INAPPROPRIATE_PATTERNS,
    "non_educational": _NON_EDUCATIONAL_PATTERNS,
}

# Threshold: consecutive triggers before parent notification
CONSECUTIVE_TRIGGER_THRESHOLD = 3

# Friendly fallback messages (randomized for variety)
FALLBACK_MESSAGES = [
    "让我们换个话题聊聊吧！你想了解什么有趣的知识？",
    "这个话题我不太擅长哦。要不要试试探索其他的？",
    "嗯，我们来聊聊别的吧！你对什么感兴趣？",
    "这个问题超出了我的范围。来探索科学知识怎么样？",
]

_FALLBACK_INDEX = 0


def _next_fallback() -> str:
    """Round-robin fallback message selection."""
    global _FALLBACK_INDEX
    msg = FALLBACK_MESSAGES[_FALLBACK_INDEX % len(FALLBACK_MESSAGES)]
    _FALLBACK_INDEX += 1
    return msg


@dataclass
class FilterResult:
    safe: bool
    filtered_text: str
    triggered_rules: list[str] = field(default_factory=list)


def filter_tutor_output(text: str, child_id: int | None = None) -> FilterResult:
    """Filter AI tutor output for content safety.

    Returns FilterResult with safe=True if text passes all rules.
    On trigger, returns friendly fallback and logs the event.
    """
    triggered: list[str] = []

    for category, patterns in RULE_CATEGORIES.items():
        for pattern in patterns:
            if pattern.search(text):
                triggered.append(category)
                break  # One hit per category is enough

    if not triggered:
        return FilterResult(safe=True, filtered_text=text)

    # Log the filter event
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    logger.warning(
        "Content safety filter triggered | child_id=%s | rules=%s | text_hash=%s",
        child_id,
        triggered,
        text_hash,
    )

    fallback = _next_fallback()
    return FilterResult(
        safe=False,
        filtered_text=fallback,
        triggered_rules=triggered,
    )


class ConsecutiveFilterTracker:
    """Track consecutive filter triggers per child for parent notification."""

    def __init__(self) -> None:
        self._counts: dict[int, int] = {}  # child_id → consecutive count

    def record_trigger(self, child_id: int) -> int:
        """Record a filter trigger. Returns current consecutive count."""
        count = self._counts.get(child_id, 0) + 1
        self._counts[child_id] = count
        return count

    def record_safe(self, child_id: int) -> None:
        """Reset counter on safe output."""
        self._counts.pop(child_id, None)

    def should_notify_parent(self, child_id: int) -> bool:
        """Check if consecutive triggers exceed threshold."""
        return self._counts.get(child_id, 0) >= CONSECUTIVE_TRIGGER_THRESHOLD

    def reset(self, child_id: int) -> None:
        """Reset after notification sent."""
        self._counts.pop(child_id, None)


# Module-level singleton
_consecutive_tracker = ConsecutiveFilterTracker()


def get_consecutive_tracker() -> ConsecutiveFilterTracker:
    """Get the module-level consecutive trigger tracker."""
    return _consecutive_tracker
