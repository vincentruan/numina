import uuid
from collections.abc import AsyncGenerator

from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import RedactedContext
from apps.agent.services.agent_temp_cache import agent_temp_cache
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.stream_events import EventStreamBuilder


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events."""
    task_id = str(uuid.uuid4())
    builder = EventStreamBuilder(capability_id=f"agent-{agent_id}", task_id=task_id)

    # 1. Fetch agent config from backend
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        yield builder.error(f"获取智能体配置失败: {e}", code="AGENT_CONFIG_ERROR").to_ndjson()
        return

    if not agent_config.get("is_enabled", True):
        yield builder.error("智能体已禁用", code="AGENT_DISABLED").to_ndjson()
        return

    # 2. Fetch AI provider config for this family
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        yield builder.error(f"获取 AI 配置失败: {e}", code="AI_CONFIG_ERROR").to_ndjson()
        return

    # 3. Build temp directory via cache
    config_data = {
        "name": agent_config["agent_name"],
        "model": agent_config.get("model") or "inherit",
        "skills": agent_config.get("skills") or [],
        "tool_groups": agent_config.get("tool_groups") or [],
        "subagent_enabled": agent_config.get("subagent_enabled", False),
    }
    agent_temp_cache.get_or_create(
        agent_id=agent_id,
        family_id=int(family_id),
        soul_md=agent_config["soul_md"],
        config_data=config_data,
    )

    # 4. Create DeerFlow adapter (reuses existing family adapter cache)
    adapter = create_family_adapter(
        family_id=family_id,
        ai_config=ai_config,
        subagent_enabled=agent_config.get("subagent_enabled", False),
        mcp_servers=None,
    )

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. Build context from available skills
    skills = agent_config.get("skills") or []
    skill_name = skills[0] if len(skills) == 1 else "agent"

    # 7. Emit session start
    yield builder.phase("connecting", {"agent_name": agent_config["agent_name"]}).to_ndjson()

    # 8. Stream via adapter
    answer_parts: list[str] = []
    thinking_started = False
    answering_started = False

    context = _build_redacted_context(family_id, message, agent_config)

    try:
        async for chunk in adapter.stream_dispatch(
            skill_name=skill_name,
            context=context,
            thread_id=thread_id,
            enable_thinking=enable_thinking,
        ):
            if chunk.type == "thinking":
                if not thinking_started:
                    yield builder.phase("thinking").to_ndjson()
                    thinking_started = True
                yield builder.token(chunk.content, is_thinking=True).to_ndjson()
            elif chunk.type == "text":
                if not answering_started:
                    yield builder.phase("answering").to_ndjson()
                    answering_started = True
                answer_parts.append(chunk.content)
                yield builder.token(chunk.content, is_thinking=False).to_ndjson()
    except Exception as e:
        yield builder.error(str(e), code="STREAM_ERROR").to_ndjson()
        return

    # 9. Emit end
    yield builder.end(
        summary="".join(answer_parts)[:200],
        tokens_used=0,
        execution_time_ms=0,
        tools_used=None,
    ).to_ndjson()


def _build_redacted_context(family_id: str, message: str, agent_config: dict) -> RedactedContext:
    """Build a minimal RedactedContext for the adapter."""
    return RedactedContext(
        family_id=family_id,
        free_text=message,
        redaction_log=[],
    )
