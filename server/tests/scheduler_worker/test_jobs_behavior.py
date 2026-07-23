"""Scheduler Worker tests — 行为分支测试（happy path / failure path / file_sync 分支）。

与 test_jobs_timing.py 的“被调用即可”冒烟测试互补：本文件验证每个 job 的
- Happy path：底层 service 以 session 调用、job 正常返回、session 在 finally 中关闭。
- Failure path：service 抛异常时 job 不外抛（捕获并记录日志），session 仍被关闭。
- file_sync_job：针对其复杂分支（无默认后端 / 解密失败 / 缓存文件缺失 /
  路径越界 / 成功上传 / 各类异常重试）逐一构造 mock 验证。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.settings import settings
from packages.storage.base import StorageError

# ── 通用 fixture ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session_local():
    """Mock SessionLocal，避免真实数据库连接；返回的 mock_session 可断言 close。"""
    mock_session = MagicMock()
    mock_session.close = MagicMock()
    with patch("apps.scheduler_worker.jobs.SessionLocal", return_value=mock_session):
        yield mock_session


# ════════════════════════════════════════════════════════════════════════════
# Job 1: fetch_rates_job
# ════════════════════════════════════════════════════════════════════════════


class TestFetchRatesJobBehavior:
    """fetch_rates_job 行为测试。"""

    def test_happy_path_closes_session(self, mock_session_local):
        """service 成功时：以 session 调用、不外抛、session 关闭。"""
        with patch(
            "packages.domain.exchange_rate.service.ExchangeRateService.fetch_and_store_rates",
            return_value=True,
        ) as mock_fetch:
            from apps.scheduler_worker.jobs import fetch_rates_job

            fetch_rates_job()

            mock_fetch.assert_called_once_with(mock_session_local)
            mock_session_local.close.assert_called_once()

    def test_service_returning_false_still_closes(self, mock_session_local):
        """service 返回 False（未成功）时：不抛异常、session 仍关闭。"""
        with patch(
            "packages.domain.exchange_rate.service.ExchangeRateService.fetch_and_store_rates",
            return_value=False,
        ):
            from apps.scheduler_worker.jobs import fetch_rates_job

            fetch_rates_job()  # 不应抛出

            mock_session_local.close.assert_called_once()

    def test_service_exception_not_propagated(self, mock_session_local):
        """service 抛异常时：job 捕获并记录，不外抛，session 仍关闭。"""
        with patch(
            "packages.domain.exchange_rate.service.ExchangeRateService.fetch_and_store_rates",
            side_effect=RuntimeError("网络超时"),
        ):
            from apps.scheduler_worker.jobs import fetch_rates_job

            fetch_rates_job()  # 不应抛出

            mock_session_local.close.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# Job 3: audit_log_purge_job
# ════════════════════════════════════════════════════════════════════════════


class TestAuditLogPurgeJobBehavior:
    """audit_log_purge_job 行为测试。

    注意：该 job 不创建 session、也无 try/except —— 异常会直接传播。
    """

    def test_happy_path_calls_with_retention_90(self, mock_session_local):
        """以 retention_days=90 调用 purge_old_audit_logs。"""
        with patch(
            "packages.domain.audit.service.purge_old_audit_logs"
        ) as mock_purge:
            from apps.scheduler_worker.jobs import audit_log_purge_job

            audit_log_purge_job()

            mock_purge.assert_called_once_with(retention_days=90)

    def test_exception_propagates(self, mock_session_local):
        """与其他 job 不同：audit_log_purge_job 不捕获异常，直接外抛。"""
        with patch(
            "packages.domain.audit.service.purge_old_audit_logs",
            side_effect=RuntimeError("DB 错误"),
        ):
            from apps.scheduler_worker.jobs import audit_log_purge_job

            with pytest.raises(RuntimeError, match="DB 错误"):
                audit_log_purge_job()


# ════════════════════════════════════════════════════════════════════════════
# Job 4: revoked_token_cleanup_job
# ════════════════════════════════════════════════════════════════════════════


class TestRevokedTokenCleanupJobBehavior:
    """revoked_token_cleanup_job 行为测试。"""

    def test_happy_path(self, mock_session_local):
        """以 session 调用清理函数、session 关闭。"""
        with patch(
            "packages.security.revoke_jti.cleanup_expired_revoked_tokens",
            return_value=5,
        ) as mock_cleanup:
            from apps.scheduler_worker.jobs import revoked_token_cleanup_job

            revoked_token_cleanup_job()

            mock_cleanup.assert_called_once_with(mock_session_local)
            mock_session_local.close.assert_called_once()

    def test_exception_not_propagated(self, mock_session_local):
        """清理函数抛异常时：不外抛、session 仍关闭。"""
        with patch(
            "packages.security.revoke_jti.cleanup_expired_revoked_tokens",
            side_effect=RuntimeError("清理失败"),
        ):
            from apps.scheduler_worker.jobs import revoked_token_cleanup_job

            revoked_token_cleanup_job()  # 不应抛出

            mock_session_local.close.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# Job 5: device_session_cleanup_job
# ════════════════════════════════════════════════════════════════════════════


class TestDeviceSessionCleanupJobBehavior:
    """device_session_cleanup_job 行为测试。"""

    def test_happy_path_calls_both(self, mock_session_local):
        """两个清理函数均以 session 调用、session 关闭。"""
        with patch(
            "packages.domain.device.service.cleanup_expired_device_sessions",
            return_value=3,
        ) as mock_expired, patch(
            "packages.domain.device.service.delete_old_revoked_sessions",
            return_value=2,
        ) as mock_purged:
            from apps.scheduler_worker.jobs import device_session_cleanup_job

            device_session_cleanup_job()

            mock_expired.assert_called_once_with(mock_session_local)
            mock_purged.assert_called_once_with(mock_session_local)
            mock_session_local.close.assert_called_once()

    def test_exception_not_propagated(self, mock_session_local):
        """第一个清理函数抛异常时：不外抛、session 仍关闭。"""
        with patch(
            "packages.domain.device.service.cleanup_expired_device_sessions",
            side_effect=RuntimeError("过期清理失败"),
        ), patch(
            "packages.domain.device.service.delete_old_revoked_sessions",
            return_value=0,
        ):
            from apps.scheduler_worker.jobs import device_session_cleanup_job

            device_session_cleanup_job()  # 不应抛出

            mock_session_local.close.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# Job 6: reminder_job
# ════════════════════════════════════════════════════════════════════════════


class TestReminderJobBehavior:
    """reminder_job 行为测试。"""

    def test_happy_path(self, mock_session_local):
        """以 session 调用 run_scheduled_checks、session 关闭。"""
        with patch(
            "packages.domain.notification.service.run_scheduled_checks"
        ) as mock_checks:
            from apps.scheduler_worker.jobs import reminder_job

            reminder_job()

            mock_checks.assert_called_once_with(mock_session_local)
            mock_session_local.close.assert_called_once()

    def test_exception_not_propagated(self, mock_session_local):
        """检测函数抛异常时：不外抛、session 仍关闭。"""
        with patch(
            "packages.domain.notification.service.run_scheduled_checks",
            side_effect=RuntimeError("通知失败"),
        ):
            from apps.scheduler_worker.jobs import reminder_job

            reminder_job()  # 不应抛出

            mock_session_local.close.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# Job 7: snapshot_job
# ════════════════════════════════════════════════════════════════════════════


class TestSnapshotJobBehavior:
    """snapshot_job 行为测试。"""

    def test_happy_path(self, mock_session_local):
        """以 session 调用 auto_generate_daily_snapshots、session 关闭。"""
        with patch(
            "packages.domain.snapshot.service.auto_generate_daily_snapshots"
        ) as mock_snapshot:
            from apps.scheduler_worker.jobs import snapshot_job

            snapshot_job()

            mock_snapshot.assert_called_once_with(mock_session_local)
            mock_session_local.close.assert_called_once()

    def test_exception_not_propagated(self, mock_session_local):
        """快照函数抛异常时：不外抛、session 仍关闭。"""
        with patch(
            "packages.domain.snapshot.service.auto_generate_daily_snapshots",
            side_effect=RuntimeError("快照失败"),
        ):
            from apps.scheduler_worker.jobs import snapshot_job

            snapshot_job()  # 不应抛出

            mock_session_local.close.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# Job 2: file_sync_job（复杂分支）
# ════════════════════════════════════════════════════════════════════════════


def _make_backend_row(*, config: str | None = "enc:cfg", backend_id: int = 11):
    """构造默认存储后端行（SimpleNamespace 模拟 ORM 对象）。"""
    return SimpleNamespace(
        id=backend_id,
        backend_type="local",
        config=config,
        is_default=True,
        is_active=True,
    )


def _make_loc(*, file_id: int = 101, retry_count: int = 0):
    """构造 FileRemoteLocation（SimpleNamespace，retry_count 需真实 int 语义）。"""
    return SimpleNamespace(
        file_id=file_id,
        backend_id=11,
        sync_status="pending",
        remote_path=None,
        remote_url=None,
        synced_at=None,
        last_error=None,
        retry_count=retry_count,
    )


def _make_cached_file(*, file_id: int = 101, local_path: str, deleted_at=None):
    """构造 CachedFile（SimpleNamespace）。"""
    return SimpleNamespace(
        id=file_id,
        local_path=local_path,
        date_dir="20260722",
        deleted_at=deleted_at,
    )


def _configure_db_query(mock_session, *, backend_row, pending, cached_files):
    """按模型类型配置 db.query(...) 的链式返回值。

    file_sync_job 内三次查询：
      1. db.query(StorageBackend).filter_by(...).first()        -> backend_row
      2. db.query(FileRemoteLocation).filter_by().filter().filter().limit().all() -> pending
      3. db.query(CachedFile).filter(...).all()                  -> cached_files
    """

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", "")
        if name == "StorageBackend":
            q.filter_by.return_value.first.return_value = backend_row
        elif name == "FileRemoteLocation":
            # filter_by(...).filter(...).filter(...).limit(...).all()
            chain = q.filter_by.return_value.filter.return_value.filter.return_value
            chain.limit.return_value.all.return_value = pending
        elif name == "CachedFile":
            q.filter.return_value.all.return_value = cached_files
        return q

    mock_session.query.side_effect = query_side_effect


@pytest.fixture
def no_real_sleep():
    """避免真实 asyncio.sleep / random.uniform 延迟。"""
    with patch("apps.scheduler_worker.jobs.asyncio.sleep", new=AsyncMock()) as mock_sleep, patch(
        "apps.scheduler_worker.jobs.random.uniform", return_value=0.0
    ):
        yield mock_sleep


class TestFileSyncJobEarlyReturn:
    """file_sync_job 提前返回分支。"""

    async def test_no_default_backend_returns_early(self, mock_session_local, no_real_sleep):
        """无默认后端行 → 直接 return，session 关闭，不触碰 backend。"""
        _configure_db_query(
            mock_session_local, backend_row=None, pending=[], cached_files=[]
        )
        with patch(
            "packages.storage.factory.get_backend_for_type"
        ) as mock_factory:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

            mock_factory.assert_not_called()
            mock_session_local.close.assert_called_once()

    async def test_decrypt_config_none_returns_early(self, mock_session_local, no_real_sleep):
        """decrypt_config 返回 None → 记录 warning 并 return，不构造 backend。"""
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(config="bad"),
            pending=[],
            cached_files=[],
        )
        with patch(
            "packages.storage.config_crypto.decrypt_config", return_value=None
        ), patch(
            "packages.storage.factory.get_backend_for_type"
        ) as mock_factory:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

            mock_factory.assert_not_called()
            mock_session_local.close.assert_called_once()


class TestFileSyncJobBranches:
    """file_sync_job 处理 pending 记录的各分支。"""

    def _patch_common(self, tmp_path, backend):
        """公共 patch：UPLOAD_DIR、decrypt_config、get_backend_for_type。"""
        return (
            patch.object(settings, "UPLOAD_DIR", str(tmp_path)),
            patch("packages.storage.config_crypto.decrypt_config", return_value={"upload_dir": str(tmp_path)}),
            patch("packages.storage.factory.get_backend_for_type", return_value=backend),
        )

    def _make_backend(self):
        backend = MagicMock()
        backend.save = AsyncMock(return_value="remote/20260722/file.bin")
        backend.get_url = MagicMock(return_value="https://cdn.example/remote/20260722/file.bin")
        backend.write_delay_range = (0.0, 0.0)
        return backend

    async def test_cached_file_missing_marks_failed(self, mock_session_local, no_real_sleep, tmp_path):
        """pending 记录无对应 CachedFile → 标记 failed + 错误信息，commit。"""
        loc = _make_loc(file_id=999)
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[],  # 无对应 cached file
        )
        backend = self._make_backend()
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "failed"
        assert loc.last_error == "本地文件记录不存在或已删除"
        backend.save.assert_not_called()
        mock_session_local.commit.assert_called()
        mock_session_local.close.assert_called_once()

    async def test_cached_file_deleted_marks_failed(self, mock_session_local, no_real_sleep, tmp_path):
        """CachedFile 已删除（deleted_at 非空）→ 标记 failed。"""
        from datetime import datetime

        loc = _make_loc(file_id=101)
        cf = _make_cached_file(
            file_id=101,
            local_path=str(tmp_path / "f.bin"),
            deleted_at=datetime.now(),
        )
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "failed"
        assert loc.last_error == "本地文件记录不存在或已删除"
        backend.save.assert_not_called()

    async def test_path_traversal_marks_failed(self, mock_session_local, no_real_sleep, tmp_path):
        """local_path 解析到 UPLOAD_DIR 之外 → 标记 failed（路径越界）。"""
        loc = _make_loc(file_id=101)
        # 指向 UPLOAD_DIR 之外的路径
        outside = tmp_path.parent / "outside_evil.bin"
        cf = _make_cached_file(file_id=101, local_path=str(outside))
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "failed"
        assert "路径越界" in loc.last_error
        backend.save.assert_not_called()

    async def test_successful_upload_marks_synced(self, mock_session_local, no_real_sleep, tmp_path):
        """成功上传 → 标记 synced，写入 remote_path/remote_url/synced_at。"""
        # 在 UPLOAD_DIR 内创建真实文件供 _read_file 读取
        real_file = tmp_path / "20260722" / "file.bin"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_bytes(b"hello-numina")

        loc = _make_loc(file_id=101)
        cf = _make_cached_file(file_id=101, local_path=str(real_file))
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.sync_status == "synced"
        assert loc.remote_path == "remote/20260722/file.bin"
        assert loc.remote_url == "https://cdn.example/remote/20260722/file.bin"
        assert loc.synced_at is not None
        backend.save.assert_awaited_once()
        # save 内容应为真实文件字节
        args, _ = backend.save.await_args
        assert args[0] == b"hello-numina"
        assert args[1] == "file.bin"
        mock_session_local.commit.assert_called()
        mock_session_local.close.assert_called_once()

    @pytest.mark.parametrize(
        ("exc", "expected_error"),
        [
            (TimeoutError(), "上传超时 (30s)"),
            (FileNotFoundError(), None),  # last_error 含“本地文件不存在”
            (StorageError("远端限流"), "远端限流"),
        ],
        ids=["timeout", "file-not-found", "storage-error"],
    )
    async def test_retryable_errors_increment_retry(
        self, mock_session_local, no_real_sleep, tmp_path, exc, expected_error
    ):
        """可重试异常 → retry_count+1；retry_count<3 时保持 pending（不标 failed）。"""
        real_file = tmp_path / "f.bin"
        real_file.write_bytes(b"x")

        loc = _make_loc(file_id=101, retry_count=0)
        cf = _make_cached_file(file_id=101, local_path=str(real_file))
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        # 三类异常统一由 backend.save 抛出（FileNotFoundError 语义上来自 _read_file，
        # 但 job 的 except 处理相同，从 save 抛出可覆盖同一分支）。
        backend.save = AsyncMock(side_effect=exc)
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.retry_count == 1
        assert loc.sync_status == "pending"  # 未达 3 次，不标 failed
        if expected_error is not None:
            assert loc.last_error == expected_error
        else:
            assert "本地文件不存在" in loc.last_error
        mock_session_local.commit.assert_called()

    @pytest.mark.parametrize(
        "exc",
        [TimeoutError(), FileNotFoundError(), StorageError("远端限流")],
        ids=["timeout", "file-not-found", "storage-error"],
    )
    async def test_retry_count_reaching_3_marks_failed(
        self, mock_session_local, no_real_sleep, tmp_path, exc
    ):
        """retry_count 已达 2 时再失败 → +1 变为 3 → 标记 failed。"""
        real_file = tmp_path / "f.bin"
        real_file.write_bytes(b"x")

        loc = _make_loc(file_id=101, retry_count=2)
        cf = _make_cached_file(file_id=101, local_path=str(real_file))
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        backend.save = AsyncMock(side_effect=exc)
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.retry_count == 3
        assert loc.sync_status == "failed"

    async def test_unexpected_exception_increments_retry(self, mock_session_local, no_real_sleep, tmp_path):
        """未分类异常（Exception 分支）→ retry_count+1，记录 str(e)。"""
        real_file = tmp_path / "f.bin"
        real_file.write_bytes(b"x")

        loc = _make_loc(file_id=101, retry_count=0)
        cf = _make_cached_file(file_id=101, local_path=str(real_file))
        _configure_db_query(
            mock_session_local,
            backend_row=_make_backend_row(),
            pending=[loc],
            cached_files=[cf],
        )
        backend = self._make_backend()
        backend.save = AsyncMock(side_effect=ValueError("意外错误"))
        p1, p2, p3 = self._patch_common(tmp_path, backend)
        with p1, p2, p3:
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()

        assert loc.retry_count == 1
        assert loc.last_error == "意外错误"
        assert loc.sync_status == "pending"

    async def test_outer_exception_closes_session(self, mock_session_local, no_real_sleep, tmp_path):
        """外层异常（如 db.query 抛错）→ 捕获记录，不外抛，session 仍关闭。"""
        mock_session_local.query.side_effect = RuntimeError("DB 连接断开")
        with patch(
            "packages.storage.config_crypto.decrypt_config", return_value={}
        ):
            from apps.scheduler_worker.jobs import file_sync_job

            await file_sync_job()  # 不应抛出

            mock_session_local.close.assert_called_once()
