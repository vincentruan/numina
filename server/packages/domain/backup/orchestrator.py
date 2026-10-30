"""Shared backup orchestration used by both the API and the scheduler job.

Uploading a backup needs the same steps wherever it is triggered: serialise
the family, refuse a payload the backend cannot store, upload it, and record
the outcome. Keeping that in one place means a manual backup and a scheduled
one cannot drift apart.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.backup_run import BackupRun
from packages.db.models.storage_backend import StorageBackend
from packages.domain.backup.service import export_family_data
from packages.storage.base import StorageBackend as StorageBackendABC
from packages.storage.base import StorageFileSizeError
from packages.storage.config_crypto import decrypt_config
from packages.storage.factory import get_backend_for_type

logger = get_logger(__name__)

BACKUP_ROOT = "backups"


def backup_path(family_id: int, when: datetime | None = None) -> str:
    """Build the remote path for a backup taken at ``when``.

    The timestamp segment lets several backups coexist for one day, which a
    manual backup needs because it never overwrites the scheduled one.
    """
    moment = when or datetime.now(UTC)
    day = moment.strftime("%Y%m%d")
    stamp = moment.strftime("%H%M%S")
    return f"{BACKUP_ROOT}/{day}/{stamp}/numina_backup_{family_id}.json"


def resolve_backend(db: Session, family_id: int) -> StorageBackendABC | None:
    """Return the family's active storage backend, or None if it has none."""
    row = (
        db.query(StorageBackend)
        .filter(StorageBackend.family_id == family_id, StorageBackend.is_active.is_(True))
        .first()
    )
    if row is None:
        return None
    config = decrypt_config(row.config)
    if config is None:
        raise ValueError(
            "存储后端配置无法解密 — 请检查 STORAGE_ENCRYPTION_KEY 是否与加密时一致"
        )
    return get_backend_for_type(row.backend_type, config)


async def create_backup(
    db: Session,
    family_id: int,
    *,
    trigger_type: str,
    when: datetime | None = None,
) -> tuple[BackupRun, dict[str, Any]]:
    """Export, upload, and record one backup.

    Returns the recorded run plus the payload. Raises on any failure after
    recording the failed run, so the caller decides whether to continue.
    """
    moment = when or datetime.now(UTC)
    payload = export_family_data(db, family_id)
    body = json.dumps(payload, ensure_ascii=False).encode()
    path = backup_path(family_id, moment)

    run = BackupRun(
        family_id=family_id,
        backup_date=moment.strftime("%Y%m%d"),
        file_path=path,
        file_size=len(body),
        status="failed",
        trigger_type=trigger_type,
        consecutive_failures=_current_failure_streak(db, family_id),
    )
    db.add(run)
    db.flush()

    try:
        backend = resolve_backend(db, family_id)
        if backend is None:
            raise ValueError("该家庭没有启用的存储后端")
        # Ask the backend to store it as-is; a payload over its limit must fail
        # loudly rather than be silently truncated or skipped.
        date_dir, _, filename = path.rpartition("/")
        uploaded = await backend.save(
            body, filename, date_dir, family_id=str(family_id)
        )
    except StorageFileSizeError as exc:
        _record_failure(
            db, run, f"备份文件过大: {exc.file_size} bytes (限制 {exc.max_size} bytes)"
        )
        raise
    except Exception as exc:
        _record_failure(db, run, str(exc))
        raise

    run.status = "success"
    run.file_path = uploaded
    run.error_message = None
    run.consecutive_failures = 0
    db.flush()
    return run, payload


def _record_failure(db: Session, run: BackupRun, message: str) -> None:
    run.status = "failed"
    run.error_message = message
    run.consecutive_failures = _current_failure_streak(db, run.family_id) + 1
    db.flush()


def _current_failure_streak(db: Session, family_id: int) -> int:
    """Consecutive failures recorded before this run."""
    latest = (
        db.query(BackupRun)
        .filter(BackupRun.family_id == family_id)
        .order_by(BackupRun.created_at.desc())
        .first()
    )
    if latest is None or latest.status == "success":
        return 0
    return latest.consecutive_failures


async def load_backup(
    db: Session, family_id: int, *, remote_path: str | None = None, backup_date: str | None = None
) -> dict[str, Any]:
    """Fetch and parse a backup from remote storage.

    The path is always resolved server-side. ``backup_date`` is validated to be
    8 digits before it contributes anything, so a client cannot inject path
    segments; when only a date is given the newest backup for that day wins.
    """
    backend = resolve_backend(db, family_id)
    if backend is None:
        raise ValueError("该家庭没有启用的存储后端")

    if remote_path is None:
        if backup_date is None or not backup_date.isdigit() or len(backup_date) != 8:
            raise ValueError("backup_date 必须为 8 位数字 (YYYYMMDD)")
        remote_path = await _newest_backup_path(backend, family_id, backup_date)

    raw = await backend.load(remote_path)
    parsed: dict[str, Any] = json.loads(raw)
    return parsed


async def _newest_backup_path(
    backend: StorageBackendABC, family_id: int, backup_date: str
) -> str:
    """Find the newest backup for a day by walking its date directory."""
    entries = await backend.list(f"{BACKUP_ROOT}/{backup_date}")
    # Layout is backups/<day>/<time>/<file>; list() on the day returns the time
    # directories, so descend into each and collect the files.
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        path = entry.get("path", "")
        if path.endswith(".json"):
            candidates.append((path, path))
            continue
        for child in await backend.list(path):
            child_path = child.get("path", "")
            if child_path.endswith(".json") and f"numina_backup_{family_id}.json" in child_path:
                candidates.append((path, child_path))

    if not candidates:
        raise FileNotFoundError(f"{backup_date} 没有可用的备份")
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def list_backups(
    db: Session, family_id: int, *, limit: int = 30, offset: int = 0
) -> list[dict[str, Any]]:
    """List backups, preferring what remote storage actually holds.

    Remote storage is authoritative: the recorded runs live in the same
    database a disaster would take with it, so after a restore they may not
    exist while the backups do.
    """
    recorded = {
        run.file_path: run
        for run in db.query(BackupRun).filter(BackupRun.family_id == family_id).all()
    }
    rows: list[dict[str, Any]] = [
        {
            "backup_date": run.backup_date,
            "file_path": run.file_path,
            "file_size": run.file_size,
            "status": run.status,
            "trigger_type": run.trigger_type,
            "created_at": run.created_at,
        }
        for run in db.query(BackupRun)
        .filter(BackupRun.family_id == family_id)
        .order_by(BackupRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    ]
    for row in rows:
        run = recorded.get(str(row["file_path"]))
        row["backup_run_id"] = str(run.id) if run else None
    return rows


def resolve_backup_path(
    db: Session, family_id: int, backup_run_id: str | None
) -> str | None:
    """Look up the recorded remote path for one of this family's backups.

    The caller passes an opaque run id, never a path, so a client cannot point
    the restore at an arbitrary object. A run id belonging to another family
    resolves to nothing rather than to that family's backup.
    """
    if backup_run_id is None:
        return None
    run = (
        db.query(BackupRun)
        .filter(BackupRun.family_id == family_id, BackupRun.id == int(backup_run_id))
        .one_or_none()
    )
    if run is None:
        raise FileNotFoundError(f"找不到备份记录: {backup_run_id}")
    return run.file_path
