"""Snapshot scheduler 入口测试。

packages.domain.snapshot.service.auto_generate_daily_snapshots 是一个
Phase-2 惰性导入委托器：把调用转发给
apps.backend.app.services.snapshot.auto_generate_daily_snapshots。

测试两条路径:
- 后端可导入 → 委托被调用且收到同一个 db
- 后端不可导入（ImportError）→ 包装成 RuntimeError
"""
import sys

import pytest

from packages.domain.snapshot import service as snapshot_service


def test_delegates_to_backend_with_same_db(packages_db, monkeypatch):
    """后端可导入 → 调用后端实现，且透传同一个 db 对象。"""
    calls = []

    def _fake_run(db):
        calls.append(db)

    # 后端模块可被导入（conftest 已 import apps.backend.app.models）。
    # 直接 monkeypatch 后端目标函数，避免真正执行快照逻辑。
    import apps.backend.app.services.snapshot as backend_snapshot

    monkeypatch.setattr(backend_snapshot, "auto_generate_daily_snapshots", _fake_run)

    snapshot_service.auto_generate_daily_snapshots(packages_db)
    assert calls == [packages_db]


def test_raises_runtime_error_when_backend_unavailable(packages_db, monkeypatch):
    """后端不可导入（ImportError）→ 抛 RuntimeError。"""
    # 把后端模块在 sys.modules 中置 None → from ... import ... 触发 ImportError。
    monkeypatch.setitem(
        sys.modules, "apps.backend.app.services.snapshot", None
    )
    with pytest.raises(RuntimeError, match="Snapshot service not available"):
        snapshot_service.auto_generate_daily_snapshots(packages_db)
