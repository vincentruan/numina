"""Verify learning-tutor app dispatches correctly."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_learning_tutor_dispatch():
    """worker.run_agent should route 'learning-tutor' app to _run_simple_app."""
    from apps.agent.services.runtime.worker import run_agent

    record = MagicMock()
    record.run_id = "run_1"
    record.thread_id = "thread_1"
    record.user_message = "Help me learn fractions"
    record.metadata = {"app": "learning-tutor", "task_id": "task_1"}
    record.on_disconnect = "continue"

    bridge = AsyncMock()

    with patch(
        "apps.agent.services.runtime.worker._run_simple_app",
        new_callable=AsyncMock,
    ) as mock_runner:
        await run_agent(
            bridge=bridge,
            run_manager=AsyncMock(),
            record=record,
            family_id="fam_1",
            user_id="user_1",
            thread_id="thread_1",
            graph_input=None,
            config=None,
        )
        mock_runner.assert_called_once()
        cfg_arg = mock_runner.call_args.args[0]
        assert cfg_arg.app_name == "learning-tutor"


@pytest.mark.asyncio
async def test_learning_tutor_config_exists():
    """learning-tutor should be in _SIMPLE_APPS config registry."""
    from apps.agent.services.runtime.worker import _SIMPLE_APPS

    assert "learning-tutor" in _SIMPLE_APPS
    cfg = _SIMPLE_APPS["learning-tutor"]
    assert cfg.skill_name == "learning-tutor"
    assert cfg.memory_enabled is False
    assert cfg.enable_thinking is False


@pytest.mark.asyncio
async def test_learning_tutor_reserved_name():
    """learning-tutor must be in RESERVED_NAMES to prevent custom skill collision."""
    from apps.backend.app.routers.ai_skills import RESERVED_NAMES

    assert "learning-tutor" in RESERVED_NAMES
    # Ensure no duplicate entries
    assert RESERVED_NAMES.count("learning-tutor") == 1


@pytest.mark.asyncio
async def test_learning_tutor_system_agent_id_exists():
    """LEARNING_TUTOR_AGENT_ID must be defined in system_ids."""
    from apps.backend.app.constants.system_ids import LEARNING_TUTOR_AGENT_ID

    assert isinstance(LEARNING_TUTOR_AGENT_ID, int)
    assert LEARNING_TUTOR_AGENT_ID > 0
