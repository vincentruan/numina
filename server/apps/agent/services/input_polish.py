"""输入润色服务（D3 DeerFlow 同步）。

轻量 LLM 单次调用（``_create_lightweight_llm`` + ``llm.ainvoke``，与
``asset_suggest`` / title 生成同形态），将用户粗略草稿改写为更清晰的提问。
无状态、无持久化、不写入 thread。已处理 ``enable_thinking: False`` 避免
Qwen3 空内容（见 ``qwen3-enable-thinking-empty-content`` 经验文档）。
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from apps.agent.services.runtime.run_extras import _create_lightweight_llm

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 4000
_MAX_OUTPUT_TOKENS = 400

_SYSTEM_PROMPT = (
    "你是数鸣的发送前提示词优化器。"
    "在用户提问发送给 AI 之前，将其粗略草稿改写为更清晰的指令。"
    "不要回答任务本身。"
    "保留用户的语言、意图、实体、文件路径、URL、代码块以及任何开头的斜杠命令前缀，原样不动。"
    "当草稿隐含了目标、范围、约束或期望输出时，将其显式化。"
    "对于「更好」「好看」「完善」等模糊质量词，转化为具体但通用的质量标准。"
    "不要编造草稿未隐含的事实、业务背景、工具、文件名、日期、指标或用户偏好。"
    "优先用一段简洁的文字或简短的项目列表。除非原草稿更长，否则控制在 180 字以内。"
    "只输出改写后的草稿，不要 markdown 包裹、解释或备选方案。"
    "【Key Invariant】如果草稿已经足够清晰（无歧义、无模糊词、意图明确），必须原样返回，不得改写。"
    "尤其不得替换、删减或重组人名、账户名、金额、电话号码等具体实体——这些是 PII，"
    "任何替换都会污染下游数据。"
)

# Strip <think>…</think> blocks (reasoning models may emit them even with
# enable_thinking=False on some providers) and stray ``` fences.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s*```\w*\s*\n?|\n?```\s*$", re.DOTALL)


def _clean_rewritten_text(text: str) -> str:
    cleaned = _THINK_RE.sub("", text)
    cleaned = _FENCE_RE.sub("", cleaned)
    return cleaned.strip()


async def polish_draft(text: str, ai_config: dict) -> tuple[str, bool]:
    """改写草稿，返回 ``(rewritten, changed)``。

    ``changed=False`` 表示改写结果与原文一致（或为空），前端据此跳过替换 +
    不显示 undo。
    """
    original = text.strip()
    if not original:
        return original, False
    if len(original) > _MAX_INPUT_CHARS:
        return original, False

    system = SystemMessage(content=_SYSTEM_PROMPT)
    human = HumanMessage(content=f"改写以下草稿，保留其意图：\n<draft>\n{original}\n</draft>")

    try:
        llm = _create_lightweight_llm(
            ai_config, temperature=0.5, max_tokens=_MAX_OUTPUT_TOKENS,
        )
        response = await llm.ainvoke([system, human])
        content = response.content.strip() if isinstance(response.content, str) else str(response.content)
    except Exception:
        logger.exception("input polish LLM call failed")
        return original, False

    rewritten = _clean_rewritten_text(content)
    if not rewritten or rewritten == original:
        return original, False
    return rewritten, True
