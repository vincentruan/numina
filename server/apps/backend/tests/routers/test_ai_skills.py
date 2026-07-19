"""RESERVED_NAMES 守护测试。

确保系统内置固定流程（KTD-8）的名字被保留，禁止 owner 创建同名 custom skill。
"""

from __future__ import annotations


def test_reserved_names_includes_finance_coach():
    """finance-coach is a system fixed-flow (KTD-8), must be reserved."""
    from apps.backend.app.routers.ai_skills import RESERVED_NAMES

    assert "finance-coach" in RESERVED_NAMES
