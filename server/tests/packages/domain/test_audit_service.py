"""Audit service 测试。

- write_audit_log: db 参数路径（加入调用方 session）与 SessionLocal 路径（自建 session）
- purge_old_audit_logs: 删除早于 retention_days 的记录，返回删除计数

purge_old_audit_logs 内部自建 SessionLocal() → 用 patch_session_local 打补丁。
它还会调用 write_audit_log（无 db，走 SessionLocal 路径）记录一条 purge 事件，
同样被 patch 到测试 session。

ENABLE_SECURITY_LOGGING 默认 True；为稳妥起见显式 monkeypatch 为 True。
"""
from datetime import datetime, timedelta

import pytest

import packages.domain.audit.service as audit_mod
from packages.core.settings import settings
from packages.db.models.security_audit_log import SecurityAuditLog


@pytest.fixture(autouse=True)
def _enable_security_logging(monkeypatch):
    """确保安全审计日志开关打开（默认 True，显式固定避免环境差异）。"""
    monkeypatch.setattr(settings, "ENABLE_SECURITY_LOGGING", True)


def _add_log(db, *, event_type="login", outcome="success", created_at=None, detail=None):
    row = SecurityAuditLog(
        event_type=event_type,
        outcome=outcome,
        detail=detail,
        created_at=created_at or datetime.now(),
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# write_audit_log
# ---------------------------------------------------------------------------


def test_write_audit_log_with_db_adds_to_caller_session(packages_db):
    """提供 db → 加入调用方 session（flush 但不 commit/close）。"""
    audit_mod.write_audit_log(
        event_type="login",
        outcome="success",
        user_id="42",
        ip_address="127.0.0.1",
        detail="test login",
        db=packages_db,
    )
    rows = packages_db.query(SecurityAuditLog).all()
    assert len(rows) == 1
    assert rows[0].event_type == "login"
    assert rows[0].outcome == "success"
    assert rows[0].detail == "test login"


def test_write_audit_log_without_db_uses_own_session(packages_db, patch_session_local):
    """不提供 db → 自建 SessionLocal() 写入。patch 后落到测试 session。"""
    patch_session_local(audit_mod)
    audit_mod.write_audit_log(event_type="logout", outcome="success", detail="bye")
    rows = packages_db.query(SecurityAuditLog).all()
    assert len(rows) == 1
    assert rows[0].event_type == "logout"


def test_write_audit_log_disabled_flag_writes_nothing(packages_db, monkeypatch):
    """ENABLE_SECURITY_LOGGING=False → 直接返回，不写库。"""
    monkeypatch.setattr(settings, "ENABLE_SECURITY_LOGGING", False)
    audit_mod.write_audit_log(event_type="login", outcome="success", db=packages_db)
    assert packages_db.query(SecurityAuditLog).count() == 0


def test_write_audit_log_fails_silently_on_bad_db(packages_db):
    """db 操作抛异常 → 静默吞掉（不向上抛）。"""
    class _BadDB:
        def add(self, obj):
            raise RuntimeError("db exploded")

        def flush(self):
            raise RuntimeError("db exploded")

    # 不应抛出
    audit_mod.write_audit_log(event_type="login", outcome="success", db=_BadDB())


# ---------------------------------------------------------------------------
# purge_old_audit_logs
# ---------------------------------------------------------------------------


def test_purge_deletes_records_older_than_retention(packages_db, patch_session_local):
    """早于 retention_days 的记录被删除，新的保留，返回删除计数。"""
    patch_session_local(audit_mod)
    now = datetime.now()
    _add_log(packages_db, event_type="old", created_at=now - timedelta(days=100))
    _add_log(packages_db, event_type="recent", created_at=now - timedelta(days=10))

    deleted = audit_mod.purge_old_audit_logs(retention_days=90)
    assert deleted == 1

    remaining = {r.event_type for r in packages_db.query(SecurityAuditLog).all()}
    # recent 保留；另外 purge 内部会写一条 audit_log_purge 事件
    assert "recent" in remaining
    assert "old" not in remaining


def test_purge_returns_zero_when_nothing_old(packages_db, patch_session_local):
    """没有过期记录 → 返回 0。"""
    patch_session_local(audit_mod)
    _add_log(packages_db, event_type="recent", created_at=datetime.now())
    deleted = audit_mod.purge_old_audit_logs(retention_days=90)
    assert deleted == 0


def test_purge_respects_custom_retention_days(packages_db, patch_session_local):
    """自定义 retention_days: 仅删除早于该窗口的记录。"""
    patch_session_local(audit_mod)
    now = datetime.now()
    _add_log(packages_db, event_type="d40", created_at=now - timedelta(days=40))
    _add_log(packages_db, event_type="d20", created_at=now - timedelta(days=20))
    _add_log(packages_db, event_type="d5", created_at=now - timedelta(days=5))

    deleted = audit_mod.purge_old_audit_logs(retention_days=30)
    assert deleted == 1  # 仅 d40

    remaining = {r.event_type for r in packages_db.query(SecurityAuditLog).all()}
    assert "d40" not in remaining
    assert "d20" in remaining
    assert "d5" in remaining


def test_purge_writes_purge_event_log(packages_db, patch_session_local):
    """purge 后写一条 audit_log_purge 审计事件。"""
    patch_session_local(audit_mod)
    _add_log(packages_db, event_type="old", created_at=datetime.now() - timedelta(days=100))
    audit_mod.purge_old_audit_logs(retention_days=90)
    events = {r.event_type for r in packages_db.query(SecurityAuditLog).all()}
    assert "audit_log_purge" in events
