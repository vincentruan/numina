"""Unit tests for services/deerflow_adapter/."""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.exceptions import (
    DeerFlowError,
    DeerFlowSkillNotFoundError,
    DeerFlowTimeoutError,
)


def _make_redacted() -> RedactedContext:
    return RedactedContext(family_id="fam-1")


class TestDeerFlowExceptions:
    def test_timeout_is_deerflow_error(self):
        assert issubclass(DeerFlowTimeoutError, DeerFlowError)

    def test_skill_not_found_is_deerflow_error(self):
        assert issubclass(DeerFlowSkillNotFoundError, DeerFlowError)


class TestDeerFlowAdapterDispatch:
    def _make_adapter(self, mock_client):
        from apps.agent.services.deerflow_adapter.client_factory import reset_client
        reset_client()
        with patch("apps.agent.services.deerflow_adapter.client_factory.get_deerflow_client", return_value=mock_client):
            from apps.agent.services.deerflow_adapter.adapter import DeerFlowAdapter
            adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
            adapter._client = mock_client
            adapter._timeout = 10
            adapter._config_path = None  # Required by _sync_dispatch
            adapter._is_family_mode = False
            return adapter

    def test_dispatch_returns_string(self):
        mock_client = MagicMock()
        mock_client.stream.return_value = iter(["分析结果"])
        adapter = self._make_adapter(mock_client)
        result = asyncio.run(adapter.dispatch("family-asset-checkup", _make_redacted(), "thread-1"))
        assert isinstance(result, str)

    def test_dispatch_collects_stream_events(self):
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class FakeEvent:
            type: str
            data: Any

        mock_client = MagicMock()
        mock_client.stream.return_value = iter([
            FakeEvent(type="messages-tuple", data={"type": "ai", "content": "第一段"}),
            FakeEvent(type="messages-tuple", data={"type": "ai", "content": "第二段"}),
        ])
        adapter = self._make_adapter(mock_client)
        result = asyncio.run(adapter.dispatch("family-asset-checkup", _make_redacted(), "thread-1"))
        assert "第一段" in result or "第二段" in result

    def test_dispatch_raises_deerflow_error_on_exception(self):
        mock_client = MagicMock()
        mock_client.stream.side_effect = RuntimeError("connection failed")
        adapter = self._make_adapter(mock_client)
        try:
            asyncio.run(adapter.dispatch("family-asset-checkup", _make_redacted(), "thread-1"))
            raise AssertionError("Should have raised")
        except DeerFlowError:
            pass

    def test_dispatch_raises_skill_not_found(self):
        mock_client = MagicMock()
        mock_client.stream.side_effect = Exception("skill not found: unknown-skill")
        adapter = self._make_adapter(mock_client)
        try:
            asyncio.run(adapter.dispatch("unknown-skill", _make_redacted(), "thread-1"))
            raise AssertionError("Should have raised")
        except DeerFlowSkillNotFoundError:
            pass

    def test_dispatch_timeout_raises_timeout_error(self):
        mock_client = MagicMock()
        # Raise TimeoutError directly from the executor to simulate timeout
        mock_client.stream.side_effect = Exception("stream timeout")
        adapter = self._make_adapter(mock_client)

        # Patch asyncio.wait_for to raise TimeoutError
        async def fake_wait_for(coro, timeout):
            raise TimeoutError()

        with patch("apps.agent.services.deerflow_adapter.adapter.asyncio.wait_for", fake_wait_for):
            try:
                asyncio.run(adapter.dispatch("family-asset-checkup", _make_redacted(), "thread-1"))
                raise AssertionError("Should have raised")
            except DeerFlowTimeoutError:
                pass


class TestClientFactory:
    def test_reset_clears_singleton(self):
        import apps.agent.services.deerflow_adapter.client_factory as cf
        from apps.agent.services.deerflow_adapter.client_factory import reset_client

        cf._client = object()  # set to something non-None
        reset_client()
        assert cf._client is None

    def test_get_client_raises_on_bad_config(self):
        from apps.agent.services.deerflow_adapter.client_factory import (
            get_deerflow_client,
            reset_client,
        )

        reset_client()
        try:
            get_deerflow_client("/nonexistent/config.yaml")
            raise AssertionError("Should have raised")
        except RuntimeError as e:
            assert "DeerFlowClient" in str(e) or "config" in str(e).lower()
