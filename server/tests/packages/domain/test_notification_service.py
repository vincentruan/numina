"""Notification scheduler 入口测试。

packages.domain.notification.service.run_scheduled_checks 是一个 Phase-2
惰性导入委托器：把调用转发给
apps.backend.app.services.notification.dispatcher.run_scheduled_checks。

测试两条路径:
- 后端可导入 → 委托被调用且收到同一个 db
- 后端不可导入（ImportError）→ 包装成 RuntimeError
"""
import sys

import pytest

from packages.domain.notification import service as notification_service


def test_delegates_to_backend_dispatcher_with_same_db(packages_db, monkeypatch):
    """后端可导入 → 调用后端 dispatcher，且透传同一个 db 对象。"""
    calls = []

    def _fake_run(db):
        calls.append(db)

    import apps.backend.app.services.notification.dispatcher as backend_dispatcher

    monkeypatch.setattr(backend_dispatcher, "run_scheduled_checks", _fake_run)

    notification_service.run_scheduled_checks(packages_db)
    assert calls == [packages_db]


def test_raises_runtime_error_when_backend_unavailable(packages_db, monkeypatch):
    """后端不可导入（ImportError）→ 抛 RuntimeError。"""
    monkeypatch.setitem(
        sys.modules,
        "apps.backend.app.services.notification.dispatcher",
        None,
    )
    with pytest.raises(RuntimeError, match="Notification dispatcher not available"):
        notification_service.run_scheduled_checks(packages_db)
