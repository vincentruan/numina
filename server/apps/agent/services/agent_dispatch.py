"""Agent-first execution entry point — Gateway path.

Replaces the old DeerFlowAdapter path with:
  BackendClient queries → EffectiveConfigBuilder → RunnableConfig
  → make_lead_agent() → astream() → NDJSON events.

No global singleton mutation. No ContextVar. No reload_app_config().
"""
import uuid
from collections.abc import AsyncGenerator

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.stream_events import EventStreamBuilder
from packages.core import get_path_manager
from packages.core.effective_config import EffectiveConfigBuilder
from packages.core.logging import get_logger

logger = get_logger(__name__)

# Lazy imports — deerflow and orchestrator may not be available in all environments.
# Module-level names allow patching in tests.
try:
    from deerflow.agents.lead_agent.agent import make_lead_agent
except ImportError:
    make_lead_agent = None

try:
    from apps.agent.services.orchestrator import _select_model
except ImportError:
    _select_model = None


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events."""
    task_id = str(uuid.uuid4())
    builder_events = EventStreamBuilder(capability_id=f"agent-{agent_id}", task_id=task_id)

    # 1. Fetch agent config
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        yield builder_events.error(f"获取智能体配置失败: {e}", code="AGENT_CONFIG_ERROR").to_ndjson()
        return

    if not agent_config.get("is_enabled", True):
        yield builder_events.error("智能体已禁用", code="AGENT_DISABLED").to_ndjson()
        return

    agent_name = agent_config["agent_name"]

    # 2. Fetch AI provider config
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        yield builder_events.error(f"获取 AI 配置失败: {e}", code="AI_CONFIG_ERROR").to_ndjson()
        return

    # 3. Multi-slot provider selection
    providers = ai_config.get("providers", [])
    if not providers:
        yield builder_events.error("未配置 AI 供应商", code="NO_PROVIDER").to_ndjson()
        return

    task_type = "thinking" if enable_thinking else "text"
    selected_provider, model_id, caps = _select_model(providers, task_type)

    # 4. Build effective config
    pm = get_path_manager()
    config_builder = EffectiveConfigBuilder(pm)

    try:
        effective = config_builder.build(
            family_id=int(family_id),
            agent_name=agent_name,
            ai_provider=selected_provider,
            agent_config=agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
    except Exception as e:
        yield builder_events.error(f"生成运行配置失败: {e}", code="CONFIG_BUILD_ERROR").to_ndjson()
        return

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. RunnableConfig with AppConfig injection
    runnable_config = {
        "configurable": {
            "thread_id": thread_id,
            "app_config": effective.config_dict,
            "user_id": family_id,
        }
    }

    # 7. Emit session start
    yield builder_events.phase("connecting", {"agent_name": agent_name}).to_ndjson()

    # 8. Create agent graph and stream
    if make_lead_agent is None:
        yield builder_events.error("Agent 运行环境未就绪", code="RUNTIME_ERROR").to_ndjson()
        return

    try:
        agent_graph = make_lead_agent(runnable_config)
    except Exception as e:
        yield builder_events.error(f"创建智能体失败: {e}", code="AGENT_CREATE_ERROR").to_ndjson()
        return

    # 9. Stream events
    answer_parts: list[str] = []
    answering_started = False

    state = {"messages": [{"role": "user", "content": message}]}

    try:
        async for event in agent_graph.astream(state, runnable_config):
            if isinstance(event, dict):
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict) and "messages" in node_output:
                        for msg in node_output["messages"]:
                            content = _extract_content(msg)
                            if content:
                                if not answering_started:
                                    yield builder_events.phase("answering").to_ndjson()
                                    answering_started = True
                                answer_parts.append(content)
                                yield builder_events.token(content, is_thinking=False).to_ndjson()
    except Exception as e:
        yield builder_events.error(str(e), code="STREAM_ERROR").to_ndjson()
        return

    # 10. Emit end
    yield builder_events.end(
        summary="".join(answer_parts)[:200],
        tokens_used=0,
        execution_time_ms=0,
        tools_used=None,
    ).to_ndjson()


def _extract_content(msg) -> str | None:
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
    return None
