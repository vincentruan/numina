"""Device session 清理函数测试。

- cleanup_expired_device_sessions: 过期且未撤销 → 标记 is_revoked=True
- delete_old_revoked_sessions: 已撤销且 last_seen_at 早于 7 天（或为 NULL）→ 硬删除

两个函数都接收 db 参数，直接传 packages_db。
注意: 实现使用 datetime.utcnow()（naive），测试时间戳也用 naive datetime 保持一致。
"""
from datetime import datetime, timedelta

from packages.db.models.device_session import DeviceSession
from packages.domain.device.service import (
    cleanup_expired_device_sessions,
    delete_old_revoked_sessions,
)


def _make_session(
    db,
    *,
    expires_at: datetime,
    is_revoked: bool = False,
    last_seen_at: datetime | None = None,
    jti: str,
) -> DeviceSession:
    """构造一条 DeviceSession。user_id/family_id 用任意值（SQLite 未强制 FK）。"""
    row = DeviceSession(
        user_id=1,
        family_id=1,
        device_name="test-device",
        refresh_jti=jti,
        expires_at=expires_at,
        is_revoked=is_revoked,
        last_seen_at=last_seen_at,
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# cleanup_expired_device_sessions
# ---------------------------------------------------------------------------


def test_cleanup_marks_expired_active_session_revoked(packages_db):
    """过期且未撤销 → 标记撤销，返回 1。"""
    s = _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(hours=1),
        is_revoked=False,
        jti="jti-expired",
    )
    updated = cleanup_expired_device_sessions(packages_db)
    assert updated == 1
    packages_db.refresh(s)
    assert s.is_revoked is True


def test_cleanup_leaves_future_session_untouched(packages_db):
    """未过期 → 不动，返回 0。"""
    s = _make_session(
        packages_db,
        expires_at=datetime.utcnow() + timedelta(days=1),
        is_revoked=False,
        jti="jti-future",
    )
    updated = cleanup_expired_device_sessions(packages_db)
    assert updated == 0
    packages_db.refresh(s)
    assert s.is_revoked is False


def test_cleanup_skips_already_revoked_expired_session(packages_db):
    """已撤销的过期会话 → 不重复计数（filter 要求 is_revoked=False）。"""
    _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(hours=1),
        is_revoked=True,
        jti="jti-already-revoked",
    )
    updated = cleanup_expired_device_sessions(packages_db)
    assert updated == 0


def test_cleanup_mixed_sessions(packages_db):
    """混合场景: 仅过期未撤销的被标记。"""
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(hours=2),
                  is_revoked=False, jti="j1")
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(hours=3),
                  is_revoked=False, jti="j2")
    _make_session(packages_db, expires_at=datetime.utcnow() + timedelta(days=1),
                  is_revoked=False, jti="j3")
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(hours=1),
                  is_revoked=True, jti="j4")
    updated = cleanup_expired_device_sessions(packages_db)
    assert updated == 2
    revoked = {s.refresh_jti for s in packages_db.query(DeviceSession).filter(
        DeviceSession.is_revoked.is_(True)).all()}
    assert revoked == {"j1", "j2", "j4"}


# ---------------------------------------------------------------------------
# delete_old_revoked_sessions
# ---------------------------------------------------------------------------


def test_delete_old_revoked_with_old_last_seen(packages_db):
    """已撤销且 last_seen_at 早于 7 天 → 删除。"""
    _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(days=10),
        is_revoked=True,
        last_seen_at=datetime.utcnow() - timedelta(days=8),
        jti="del-old",
    )
    deleted = delete_old_revoked_sessions(packages_db)
    assert deleted == 1
    assert packages_db.query(DeviceSession).count() == 0


def test_delete_old_revoked_null_last_seen_branch_is_unreachable(packages_db):
    """schema 层面 last_seen_at 是 NOT NULL → 源代码 or_ 的 .is_(None) 分支不可达。

    DeviceSession.last_seen_at 列定义为 Mapped[datetime]（非 Optional）且带
    server_default=func.now()，数据库层 NOT NULL 约束拒绝真正的 NULL：
    通过 ORM 传 None 会被 server_default 覆盖为当前时间；直接 Core INSERT NULL
    会触发 IntegrityError。因此 delete_old_revoked_sessions 中
    `DeviceSession.last_seen_at.is_(None)` 永远匹配不到任何行（死分支）。
    此测试固定这一事实：传 None 的会话被当作「最近见过」而保留。
    """
    s = _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(days=10),
        is_revoked=True,
        last_seen_at=None,  # server_default 覆盖为 now → 在 7 天窗口内 → 保留
        jti="null-becomes-now",
    )
    packages_db.refresh(s)
    assert s.last_seen_at is not None  # server_default 已填充
    deleted = delete_old_revoked_sessions(packages_db)
    assert deleted == 0  # last_seen_at=now 在窗口内，未删除


def test_delete_keeps_recently_seen_revoked_session(packages_db):
    """已撤销但 last_seen_at 在 7 天内 → 保留。"""
    _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(days=10),
        is_revoked=True,
        last_seen_at=datetime.utcnow() - timedelta(days=2),
        jti="keep-recent",
    )
    deleted = delete_old_revoked_sessions(packages_db)
    assert deleted == 0
    assert packages_db.query(DeviceSession).count() == 1


def test_delete_keeps_active_session_regardless_of_age(packages_db):
    """未撤销（活跃）会话即使很旧 → 保留（filter 要求 is_revoked=True）。"""
    _make_session(
        packages_db,
        expires_at=datetime.utcnow() - timedelta(days=30),
        is_revoked=False,
        last_seen_at=datetime.utcnow() - timedelta(days=30),
        jti="keep-active",
    )
    deleted = delete_old_revoked_sessions(packages_db)
    assert deleted == 0
    assert packages_db.query(DeviceSession).count() == 1


def test_delete_mixed_sessions(packages_db):
    """混合场景: 仅删除「已撤销 且 last_seen 旧」的会话。"""
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(days=10),
                  is_revoked=True, last_seen_at=datetime.utcnow() - timedelta(days=9),
                  jti="d1")  # 删
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(days=20),
                  is_revoked=True, last_seen_at=datetime.utcnow() - timedelta(days=15),
                  jti="d2")  # 删
    _make_session(packages_db, expires_at=datetime.utcnow() - timedelta(days=10),
                  is_revoked=True, last_seen_at=datetime.utcnow() - timedelta(days=1),
                  jti="k1")  # 留（最近见过）
    _make_session(packages_db, expires_at=datetime.utcnow() + timedelta(days=1),
                  is_revoked=False, last_seen_at=datetime.utcnow() - timedelta(days=30),
                  jti="k2")  # 留（活跃）
    deleted = delete_old_revoked_sessions(packages_db)
    assert deleted == 2
    remaining = {s.refresh_jti for s in packages_db.query(DeviceSession).all()}
    assert remaining == {"k1", "k2"}
