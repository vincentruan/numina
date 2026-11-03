"""Tests for the thread_search tool (T25 U5)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.runtime.thread_search_tool import (
    _matches_query,
    _search,
    _snippet,
    build_thread_search_tool,
)


def _session(
    thread_id: str = "t1",
    title: str | None = None,
    snippet: str | None = None,
    source: str | None = "numina",
) -> dict:
    return {
        "thread_id": thread_id,
        "title": title,
        "last_message_summary": snippet,
        "source": source,
        "updated_at": "2026-11-03T00:00:00Z",
    }


class TestMatchesQuery:
    """Case-insensitive substring matching on title + last_message_summary."""

    def test_empty_query_matches_all(self) -> None:
        assert _matches_query(_session(title="Anything"), "") is True

    def test_title_match(self) -> None:
        assert _matches_query(_session(title="Investment analysis"), "investment") is True

    def test_snippet_match(self) -> None:
        assert (
            _matches_query(_session(title="Other", snippet="budget is ¥50,000"), "budget")
            is True
        )

    def test_no_match(self) -> None:
        assert (
            _matches_query(_session(title="Other", snippet="hello"), "investment")
            is False
        )

    def test_case_insensitive(self) -> None:
        assert _matches_query(_session(title="INVESTMENT"), "investment") is True

    def test_whitespace_only_query_matches_all(self) -> None:
        assert _matches_query(_session(title="X"), "   ") is True


class TestSnippet:
    """Snippet extraction from last_message_summary."""

    def test_returns_summary_truncated(self) -> None:
        session = _session(snippet="a" * 500)
        assert len(_snippet(session)) == 200

    def test_returns_short_summary_untouched(self) -> None:
        session = _session(snippet="short")
        assert _snippet(session) == "short"

    def test_returns_none_when_absent(self) -> None:
        assert _snippet(_session(snippet=None)) is None
        assert _snippet(_session(snippet="")) is None


class TestSearch:
    """Backend-call + filter + JSON output."""

    @pytest.mark.asyncio
    async def test_returns_matching_sessions(self) -> None:
        sessions = [
            _session("t1", title="Investment analysis"),
            _session("t2", title="Budget review"),
            _session("t3", title="Investment followup"),
        ]
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=(sessions, 3)),
        ):
            raw = await _search("fam_1", "investment")
            results = json.loads(raw)

        assert len(results) == 2
        assert {r["thread_id"] for r in results} == {"t1", "t3"}
        assert all("snippet" in r for r in results)

    @pytest.mark.asyncio
    async def test_empty_query_returns_recent(self) -> None:
        sessions = [_session(f"t{i}", title=f"t{i}") for i in range(5)]
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=(sessions, 5)),
        ):
            raw = await _search("fam_1", "")
            results = json.loads(raw)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_limit_clamped_to_20(self) -> None:
        sessions = [_session(f"t{i}", title="match") for i in range(30)]
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=(sessions, 30)),
        ):
            raw = await _search("fam_1", "match", limit=100)
            results = json.loads(raw)

        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_backend_failure_returns_error_payload(self) -> None:
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(side_effect=RuntimeError("backend down")),
        ):
            raw = await _search("fam_1", "q")
            page = json.loads(raw)

        assert "error" in page
        assert "backend_unavailable" in page["error"]

    @pytest.mark.asyncio
    async def test_snippet_in_result(self) -> None:
        sessions = [_session("t1", title="Budget", snippet="¥50,000 monthly")]
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=(sessions, 1)),
        ):
            raw = await _search("fam_1", "budget")
            results = json.loads(raw)

        assert results[0]["snippet"] == "¥50,000 monthly"

    @pytest.mark.asyncio
    async def test_snippet_null_when_absent(self) -> None:
        sessions = [_session("t1", title="X", snippet=None)]
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=(sessions, 1)),
        ):
            raw = await _search("fam_1", "x")
            results = json.loads(raw)

        assert results[0]["snippet"] is None


class TestToolFactory:
    """build_thread_search_tool returns a usable StructuredTool."""

    def test_tool_has_expected_name(self) -> None:
        tool = build_thread_search_tool("fam_1")
        assert tool.name == "thread_search"

    @pytest.mark.asyncio
    async def test_tool_invocation_calls_search_with_bound_family(self) -> None:
        tool = build_thread_search_tool("fam_bound")
        with patch(
            "apps.agent.core.backend_client.list_sessions",
            new=AsyncMock(return_value=([], 0)),
        ) as mock:
            await tool.ainvoke({"query": "anything"})

        mock.assert_awaited_once()
        call_args = mock.await_args
        assert call_args.args[0] == "fam_bound"
