"""Tests for packages.security.revoke_jti — JTI 撤销管理 (DB 持久化).

revoke_jti 模块在导入时 `from packages.db.session import SessionLocal`,
持有自己的引用, 因此每个测试需用 `patch_session_local(revoke_mod)` 把它
指向测试用的内存 SQLite session (见 tests/packages/conftest.py).
"""

from __future__ import annotations

import time

import pytest

import packages.security.revoke_jti as revoke_mod
from packages.core.settings import settings
from packages.db.models.revoked_token import RevokedToken


@pytest.fixture(autouse=True)
def _patch_db(patch_session_local):
    """自动把 revoke_mod.SessionLocal 指向测试 DB."""
    patch_session_local(revoke_mod)


def _insert_revoked(
    packages_db,
    *,
    jti: str | None,
    user_id: str | None,
    revoked_at: float,
    expires_at: float,
) -> RevokedToken:
    """直接往测试库插一条撤销记录 (用于精确控制 expires_at / revoked_at)."""
    rec = RevokedToken(
        jti=jti, user_id=user_id, revoked_at=revoked_at, expires_at=expires_at
    )
    packages_db.add(rec)
    packages_db.flush()
    return rec


# ---------------------------------------------------------------------------
# revoke_jti + _is_jti_revoked
# ---------------------------------------------------------------------------


def test_revoke_jti_marks_jti_revoked(packages_db):
    revoke_mod.revoke_jti("jti-1", ttl_seconds=60)
    assert revoke_mod._is_jti_revoked("jti-1") is True


def test_is_jti_revoked_unknown_jti_returns_false(packages_db):
    assert revoke_mod._is_jti_revoked("never-revoked") is False


def test_revoke_jti_persists_expiry(packages_db):
    """revoke_jti 写入的 expires_at 应约为 now + ttl."""
    before = time.time()
    revoke_mod.revoke_jti("jti-ttl", ttl_seconds=120)
    after = time.time()
    rec = packages_db.query(RevokedToken).filter_by(jti="jti-ttl").one()
    assert before + 120 <= rec.expires_at <= after + 120
    assert rec.user_id is None


def test_is_jti_revoked_ignores_expired_record(packages_db):
    """expires_at <= now 的记录视为未撤销 (查询过滤 expires_at > now)."""
    now = time.time()
    _insert_revoked(
        packages_db, jti="jti-expired", user_id=None, revoked_at=now - 100, expires_at=now - 1
    )
    assert revoke_mod._is_jti_revoked("jti-expired") is False


def test_is_jti_revoked_only_matches_target_jti(packages_db):
    """撤销一个 JTI 不影响其它 JTI."""
    revoke_mod.revoke_jti("jti-A", ttl_seconds=60)
    assert revoke_mod._is_jti_revoked("jti-A") is True
    assert revoke_mod._is_jti_revoked("jti-B") is False


# ---------------------------------------------------------------------------
# revoke_jti_atomic — 原子插入, 竞争时仅一方获胜
# ---------------------------------------------------------------------------


def test_revoke_jti_atomic_first_call_wins(packages_db):
    assert revoke_mod.revoke_jti_atomic("jti-atomic", ttl_seconds=60) is True
    assert revoke_mod._is_jti_revoked("jti-atomic") is True


def test_revoke_jti_atomic_duplicate_returns_false(packages_db):
    """同一 JTI 第二次原子撤销返回 False (INSERT OR IGNORE 不覆盖)."""
    assert revoke_mod.revoke_jti_atomic("jti-dup", ttl_seconds=60) is True
    assert revoke_mod.revoke_jti_atomic("jti-dup", ttl_seconds=60) is False
    # 仍只有一条记录
    count = packages_db.query(RevokedToken).filter_by(jti="jti-dup").count()
    assert count == 1


def test_revoke_jti_atomic_distinct_jtis_independent(packages_db):
    assert revoke_mod.revoke_jti_atomic("jti-x", ttl_seconds=60) is True
    assert revoke_mod.revoke_jti_atomic("jti-y", ttl_seconds=60) is True


# ---------------------------------------------------------------------------
# revoke_all_user_tokens + _is_token_revoked_for_user
# ---------------------------------------------------------------------------


def test_revoke_all_user_tokens_revokes_old_iat(packages_db):
    """iat 早于撤销时间 -> 视为已撤销."""
    now = time.time()
    revoke_mod.revoke_all_user_tokens("user-1")
    # iat 明显早于 revoked_at
    assert revoke_mod._is_token_revoked_for_user("user-1", iat=now - 3600) is True


def test_is_token_revoked_for_user_iat_after_revoke_returns_false(packages_db):
    """iat 晚于撤销时间 (撤销后重新签发的 token) -> 未撤销."""
    revoke_mod.revoke_all_user_tokens("user-2")
    future_iat = time.time() + 3600
    assert revoke_mod._is_token_revoked_for_user("user-2", iat=future_iat) is False


def test_is_token_revoked_for_user_unknown_user_returns_false(packages_db):
    assert revoke_mod._is_token_revoked_for_user("ghost-user", iat=time.time()) is False


def test_revoke_all_user_tokens_accepts_int_user_id(packages_db):
    """user_id 支持 int, 内部转 str 存储."""
    now = time.time()
    revoke_mod.revoke_all_user_tokens(12345)
    assert revoke_mod._is_token_revoked_for_user(12345, iat=now - 10) is True
    assert revoke_mod._is_token_revoked_for_user("12345", iat=now - 10) is True


def test_revoke_all_user_tokens_expiry_uses_refresh_token_days(packages_db):
    """user 级撤销的 expires_at 应约为 now + (REFRESH_TOKEN_EXPIRE_DAYS+1) 天."""
    before = time.time()
    revoke_mod.revoke_all_user_tokens("user-ttl")
    after = time.time()
    expected = (settings.REFRESH_TOKEN_EXPIRE_DAYS + 1) * 24 * 3600
    rec = packages_db.query(RevokedToken).filter_by(user_id="user-ttl").one()
    assert before + expected <= rec.expires_at <= after + expected
    assert rec.jti is None


def test_is_token_revoked_for_user_ignores_expired_record(packages_db):
    """user 级撤销记录过期后, 不再判定为撤销."""
    now = time.time()
    _insert_revoked(
        packages_db,
        jti=None,
        user_id="user-expired",
        revoked_at=now - 200,
        expires_at=now - 1,  # 已过期
    )
    assert revoke_mod._is_token_revoked_for_user("user-expired", iat=now - 100) is False


def test_is_token_revoked_for_user_isolated_between_users(packages_db):
    """撤销 user-A 不影响 user-B."""
    now = time.time()
    revoke_mod.revoke_all_user_tokens("user-A")
    assert revoke_mod._is_token_revoked_for_user("user-A", iat=now - 10) is True
    assert revoke_mod._is_token_revoked_for_user("user-B", iat=now - 10) is False


# ---------------------------------------------------------------------------
# cleanup_expired_revoked_tokens — 清理过期记录
# ---------------------------------------------------------------------------


def test_cleanup_removes_only_expired(packages_db):
    """只删除 expires_at < now 的记录, 返回删除条数."""
    now = time.time()
    # 2 条过期
    _insert_revoked(packages_db, jti="old-1", user_id=None, revoked_at=now - 200, expires_at=now - 10)
    _insert_revoked(packages_db, jti="old-2", user_id=None, revoked_at=now - 200, expires_at=now - 5)
    # 1 条未过期
    _insert_revoked(packages_db, jti="live-1", user_id=None, revoked_at=now, expires_at=now + 3600)

    deleted = revoke_mod.cleanup_expired_revoked_tokens(packages_db)
    assert deleted == 2

    remaining = {r.jti for r in packages_db.query(RevokedToken).all()}
    assert remaining == {"live-1"}


def test_cleanup_returns_zero_when_nothing_expired(packages_db):
    now = time.time()
    _insert_revoked(packages_db, jti="live", user_id=None, revoked_at=now, expires_at=now + 3600)
    assert revoke_mod.cleanup_expired_revoked_tokens(packages_db) == 0


def test_cleanup_handles_empty_table(packages_db):
    assert revoke_mod.cleanup_expired_revoked_tokens(packages_db) == 0
