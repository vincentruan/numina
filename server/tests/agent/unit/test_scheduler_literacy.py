"""Test scheduler literacy report job."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_enumerates_families():
    """The scheduler job iterates AI-enabled families and generates reports."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    with patch(
        "apps.agent.app.scheduler.backend_client.get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111", "222"],
    ), patch(
        "apps.agent.app.scheduler.backend_client.get_literacy_children",
        new_callable=AsyncMock,
        return_value=[{"child_id": "333", "display_name": "小宝"}],
    ), patch(
        "apps.agent.app.scheduler.backend_client.generate_literacy_report",
        new_callable=AsyncMock,
    ) as mock_gen, patch(
        "apps.agent.app.scheduler.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await generate_weekly_literacy_reports()

    assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_handles_failure():
    """One family failure doesn't abort the entire run."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    call_count = 0

    async def flaky_gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated failure")

    with patch(
        "apps.agent.app.scheduler.backend_client.get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111", "222"],
    ), patch(
        "apps.agent.app.scheduler.backend_client.get_literacy_children",
        new_callable=AsyncMock,
        return_value=[{"child_id": "333"}],
    ), patch(
        "apps.agent.app.scheduler.backend_client.generate_literacy_report",
        side_effect=flaky_gen,
    ), patch(
        "apps.agent.app.scheduler.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await generate_weekly_literacy_reports()

    assert call_count == 2


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_skips_children_fetch_failure():
    """If fetching children fails for a family, that family is skipped."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    with patch(
        "apps.agent.app.scheduler.backend_client.get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111", "222"],
    ), patch(
        "apps.agent.app.scheduler.backend_client.get_literacy_children",
        new_callable=AsyncMock,
        side_effect=RuntimeError("backend down"),
    ), patch(
        "apps.agent.app.scheduler.backend_client.generate_literacy_report",
        new_callable=AsyncMock,
    ) as mock_gen, patch(
        "apps.agent.app.scheduler.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await generate_weekly_literacy_reports()

    assert mock_gen.call_count == 0


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_skips_empty_child_id():
    """Children without child_id are skipped."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    with patch(
        "apps.agent.app.scheduler.backend_client.get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111"],
    ), patch(
        "apps.agent.app.scheduler.backend_client.get_literacy_children",
        new_callable=AsyncMock,
        return_value=[{"child_id": "", "display_name": "NoID"}],
    ), patch(
        "apps.agent.app.scheduler.backend_client.generate_literacy_report",
        new_callable=AsyncMock,
    ) as mock_gen, patch(
        "apps.agent.app.scheduler.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await generate_weekly_literacy_reports()

    assert mock_gen.call_count == 0
