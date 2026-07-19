"""Provider selection + retry helpers shared across agent dispatch paths.

U8 (Resolved-10): the ``Orchestrator`` class and its ``dispatch`` method have
been deleted — all AI capabilities now route through ``stream_run`` agents
(numina / asset-report / import-parse) in ``runtime/worker.py`` or lightweight
LLM single calls (suggest) in ``routers/suggest.py``. This module retains the
module-level helpers that ``agent_dispatch.py`` still imports
(``_fire_and_forget`` + ``_select_model``, with try/except fallback) plus the
provider-selection / circuit-breaker helpers they share.
"""

import asyncio
import logging
import random

logger = logging.getLogger(__name__)


def _select_model(providers: list[dict], task_type: str) -> tuple[dict, str, list[str]]:
    """基于任务类型从 providers 列表中选择合适的模型。

    Args:
        providers: 供应商列表（已按优先级排序、已过滤熔断），每个包含 config_id 和 3 个模型槽位
        task_type: 任务类型 ("thinking" / "vision" / "text")

    Returns:
        (selected_provider_dict, model_id, selected_capabilities) — 返回完整 provider dict、
        选中的 model_id，以及选中槽位的 capabilities 列表（用于 thinking 能力判断）

    Raises:
        ValueError: providers 列表为空
    """
    if not providers:
        raise ValueError("providers list is empty — no available AI provider")

    required_capability: str
    if task_type == "thinking":
        required_capability = "deep_thinking"
    elif task_type == "vision":
        required_capability = "vision_understanding"
    else:
        required_capability = "text_generation"

    # 遍历 providers，检查每个槽位
    for provider in providers:
        # 检查槽位1 (model_id / ai_model_id)
        caps_1: list[str] = provider.get("model_1_capabilities", [])
        if required_capability in caps_1 and provider.get("ai_model_id"):
            return provider, provider["ai_model_id"], caps_1

        # 检查槽位2 (model_2_id)
        caps_2: list[str] = provider.get("model_2_capabilities", [])
        if required_capability in caps_2 and provider.get("model_2_id"):
            return provider, provider["model_2_id"], caps_2

        # 检查槽位3 (model_3_id)
        caps_3: list[str] = provider.get("model_3_capabilities", [])
        if required_capability in caps_3 and provider.get("model_3_id"):
            return provider, provider["model_3_id"], caps_3

    # Fallback: 无匹配能力时返回第一个 provider 的槽位1
    first_provider = providers[0]
    fallback_model_id = first_provider.get("ai_model_id", "")
    fallback_caps: list[str] = first_provider.get("model_1_capabilities", [])
    logger.warning(
        "[orchestrator] _select_model: no provider with capability '%s', fallback to model='%s'",
        required_capability,
        fallback_model_id,
    )
    return first_provider, fallback_model_id, fallback_caps


def _is_transient_error(error_type: str) -> bool:
    """Check if error type is transient (can cascade to next provider)."""
    return error_type.startswith("transient_") or error_type in (
        "DeerFlowTimeoutError",
        "ConnectionError",
        "TimeoutError",
    )


def _should_route_to_half_open() -> bool:
    """Decide whether to route traffic to a half-open provider (10% chance).

    Callers must filter providers to those with circuit_state == 'half_open'
    before invoking this function.
    """
    return random.random() < 0.1


def _select_provider_with_retry(
    providers: list[dict],
    task_type: str,
    attempted_config_ids: set[str],
) -> tuple[dict, str, list[str]] | None:
    """Select next provider for retry, considering half-open routing.

    Args:
        providers: List of providers sorted by display_order
        task_type: Model task type (thinking/vision/text)
        attempted_config_ids: Set of config_ids already tried

    Returns:
        (provider, model_id, capabilities) when a provider with the required
        capability is found, otherwise None. Returns None rather than falling
        back to a capability-mismatched provider, so the caller fails cleanly
        instead of silently degrading the task.
    """
    required_capability: str
    if task_type == "thinking":
        required_capability = "deep_thinking"
    elif task_type == "vision":
        required_capability = "vision_understanding"
    else:
        required_capability = "text_generation"

    # Filter providers not yet attempted
    available_providers = [
        p for p in providers if p.get("config_id") not in attempted_config_ids
    ]

    if not available_providers:
        return None

    # Prefer half_open providers for recovery testing (10% chance)
    half_open_providers = [
        p for p in available_providers if p.get("circuit_state") == "half_open"
    ]
    if half_open_providers and _should_route_to_half_open():
        # Use half_open provider for 10% traffic
        for provider in half_open_providers:
            caps = provider.get("model_1_capabilities", [])
            if required_capability in caps and provider.get("ai_model_id"):
                return provider, provider["ai_model_id"], caps

    # Normal selection: check each provider's capabilities
    for provider in available_providers:
        # Skip providers with permanent circuit state
        circuit_state = provider.get("circuit_state", "closed")
        if circuit_state == "open":
            # Open provider should not be in list, but check anyway
            continue

        caps_1 = provider.get("model_1_capabilities", [])
        if required_capability in caps_1 and provider.get("ai_model_id"):
            return provider, provider["ai_model_id"], caps_1

        caps_2 = provider.get("model_2_capabilities", [])
        if required_capability in caps_2 and provider.get("model_2_id"):
            return provider, provider["model_2_id"], caps_2

        caps_3 = provider.get("model_3_capabilities", [])
        if required_capability in caps_3 and provider.get("model_3_id"):
            return provider, provider["model_3_id"], caps_3

    # No provider with required capability — fail cleanly so caller can return
    # an error message rather than silently degrading to a mismatched provider.
    return None


def _fire_and_forget(coro: "asyncio.Coroutine") -> None:  # type: ignore[type-arg]
    """Schedule a coroutine as a fire-and-forget task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(coro)
    task.add_done_callback(
        lambda t: t.exception() and logger.warning("fire-and-forget task failed: %s", t.exception())
    )


# Module-level adapter factory — exposed for patching in tests
_deerflow_adapter = None


# U8 (Resolved-10): the ``Orchestrator`` class + ``dispatch`` method have been
# deleted. All AI capabilities now route through either:
#   - ``stream_run`` agent (numina / asset-report / import-parse) via the worker,
#   - lightweight LLM single call (suggest) via ``_create_lightweight_llm``.
# The module-level helpers below (``_select_model`` / ``_fire_and_forget`` /
# ``_select_provider_with_retry`` / ``_is_transient_error`` /
# ``_should_route_to_half_open``) are retained because ``agent_dispatch.py``
# imports ``_fire_and_forget`` + ``_select_model`` (with try/except fallback).

