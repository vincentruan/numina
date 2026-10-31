import asyncio
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category import Category
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.user import User
from packages.core.logging import get_logger
from packages.db.session import SessionLocal

logger = get_logger(__name__)

router = APIRouter(prefix="/import", tags=["import"])


class ImportRequest(BaseModel):
    mode: str = "incremental"  # "incremental" or "full"
    data: dict


@router.post("/json")
def import_json(
    req: ImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_id = user.family_id
    data = req.data
    stats = {"assets": 0, "liabilities": 0, "categories": 0, "tags": 0}

    if req.mode == "full":
        # Delete existing user data (not system categories)
        db.query(Liability).filter(Liability.family_id == family_id).delete()
        db.query(Asset).filter(Asset.family_id == family_id).delete()
        db.query(Tag).filter(Tag.family_id == family_id).delete()
        db.query(Category).filter(Category.family_id == family_id).delete()
        db.flush()

    # Import custom categories
    category_map: dict[str, str] = {}  # name -> id
    existing_cats = db.query(Category).filter(
        (Category.family_id == family_id) | (Category.family_id.is_(None))
    ).all()
    for c in existing_cats:
        category_map[c.name] = str(c.id)

    for cat_data in data.get("categories", []):
        if cat_data["name"] not in category_map:
            cat = Category(
                family_id=family_id,
                name=cat_data["name"],
                icon=cat_data.get("icon", "📦"),
                color=cat_data.get("color", "#999999"),
                asset_type=cat_data.get("asset_type", "physical"),
            )
            db.add(cat)
            db.flush()
            category_map[cat.name] = str(cat.id)
            stats["categories"] += 1

    # Import tags
    tag_map: dict[str, str] = {}  # name -> id
    existing_tags = db.query(Tag).filter(Tag.family_id == family_id).all()
    for t in existing_tags:
        tag_map[t.name] = str(t.id)

    for tag_data in data.get("tags", []):
        if tag_data["name"] not in tag_map:
            tag = Tag(
                family_id=family_id,
                name=tag_data["name"],
                color=tag_data.get("color", "#1989fa"),
            )
            db.add(tag)
            db.flush()
            tag_map[tag.name] = str(tag.id)
            stats["tags"] += 1

    # Import assets
    for asset_data in data.get("assets", []):
        cat_id = category_map.get(asset_data.get("category_name", ""))
        if not cat_id:
            cat_id = asset_data.get("category_id")

        asset = Asset(
            user_id=user.id,
            family_id=family_id,
            category_id=cat_id,
            name=asset_data["name"],
            asset_type=asset_data.get("asset_type", "physical"),
            purchase_price=asset_data.get("purchase_price"),
            current_value=asset_data.get("current_value"),
            currency=asset_data.get("currency", "CNY"),
            purchase_date=_parse_date(asset_data.get("purchase_date")),
            status=asset_data.get("status", "in_use"),
            location=asset_data.get("location"),
            institution=asset_data.get("institution"),
            interest_rate=asset_data.get("interest_rate"),
            maturity_date=_parse_date(asset_data.get("maturity_date")),
            expected_lifespan_days=asset_data.get("expected_lifespan_days"),
            annual_maintenance_cost=asset_data.get("annual_maintenance_cost"),
            usage_frequency=asset_data.get("usage_frequency"),
            notes=asset_data.get("notes"),
            is_archived=asset_data.get("is_archived", False),
        )
        # Link tags by name
        tag_names = asset_data.get("tag_names", [])
        if tag_names:
            tag_ids = [tag_map[n] for n in tag_names if n in tag_map]
            if tag_ids:
                tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
                asset.tags = tags
        db.add(asset)
        stats["assets"] += 1

    # Import liabilities
    for liab_data in data.get("liabilities", []):
        liab = Liability(
            user_id=user.id,
            family_id=family_id,
            category=liab_data.get("category", "other"),
            name=liab_data["name"],
            original_amount=liab_data["original_amount"],
            remaining_amount=liab_data["remaining_amount"],
            monthly_payment=liab_data.get("monthly_payment"),
            interest_rate=liab_data.get("interest_rate"),
            start_date=_parse_date(liab_data.get("start_date")),
            end_date=_parse_date(liab_data.get("end_date")),
            institution=liab_data.get("institution"),
            notes=liab_data.get("notes"),
            is_active=liab_data.get("is_active", True),
        )
        db.add(liab)
        stats["liabilities"] += 1

    db.commit()
    return {"detail": "导入成功", "stats": stats}


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None


# ── Family backup / restore ───────────────────────────────────────────────────
#
# Backup and restore are owner-only: restore replaces every record the family
# owns, and a backup contains the family's encrypted credential blobs. That is
# the same sensitivity as transferring ownership, not ordinary member work.

_backup_tasks: dict[str, dict] = {}


class RestoreRequest(BaseModel):
    backup_run_id: str | None = None
    backup_date: str | None = None


class BackupRequest(BaseModel):
    pass


@router.post("/backup")
async def create_family_backup(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """Trigger an immediate backup and return its location."""
    from packages.domain.backup.orchestrator import create_backup

    try:
        run, _ = await create_backup(db, user.family_id, trigger_type="manual")
    except Exception as exc:
        raise AppError(
            ErrorCode.BACKUP_FAILED, details={"reason": str(exc)}
        ) from exc
    db.commit()
    return {
        "backup_run_id": str(run.id),
        "backup_date": run.backup_date,
        "file_path": run.file_path,
        "file_size": run.file_size,
    }


@router.get("/backups")
def list_family_backups(
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """List this family's backups, most recent first."""
    from packages.domain.backup.orchestrator import list_backups

    items = list_backups(db, user.family_id, limit=limit, offset=offset)
    return {"items": items}


@router.post("/restore")
async def restore_family_data(
    req: RestoreRequest,
    dry_run: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """Preview or perform a full replacement of this family's data."""
    from packages.domain.backup.orchestrator import load_backup, resolve_backup_path
    from packages.domain.backup.service import import_family_data, preview_restore

    try:
        remote_path = resolve_backup_path(db, user.family_id, req.backup_run_id)
        payload = await load_backup(
            db, user.family_id, remote_path=remote_path, backup_date=req.backup_date
        )
    except FileNotFoundError as exc:
        raise AppError(ErrorCode.BACKUP_NOT_FOUND, details={"reason": str(exc)}) from exc
    except ValueError as exc:
        raise AppError(ErrorCode.BACKUP_INVALID, details={"reason": str(exc)}) from exc

    if dry_run:
        return preview_restore(db, user.family_id, payload)

    try:
        stats = import_family_data(db, user.family_id, user.id, payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise AppError(ErrorCode.BACKUP_INVALID, details={"reason": str(exc)}) from exc
    return {"detail": "恢复成功", "stats": stats}


@router.post("/restore-files")
async def restore_family_files(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """Start re-downloading this family's synced files."""
    from packages.domain.backup.orchestrator import resolve_backend

    backend = resolve_backend(db, user.family_id)
    if backend is None:
        raise AppError(ErrorCode.BACKUP_INVALID, details={"reason": "没有启用的存储后端"})

    task_id = _new_task_id()
    _backup_tasks[task_id] = {
        "status": "running",
        "files_completed": 0,
        "files_total": 0,
        "files_failed": 0,
        "failed_files": [],
    }
    asyncio.create_task(_restore_files_worker(task_id, user.family_id))
    return {"task_id": task_id}


@router.get("/restore-files/{task_id}")
def get_restore_files_progress(
    task_id: str,
    user: User = Depends(require_owner),
):
    task = _backup_tasks.get(task_id)
    if task is None:
        raise AppError(ErrorCode.NOT_FOUND, details={"task_id": task_id})
    return task


def _new_task_id() -> str:
    return uuid.uuid4().hex


async def _restore_files_worker(task_id: str, family_id: int) -> None:
    """Re-download each synced remote file into the local upload directory."""
    from packages.db.models.cached_file import CachedFile
    from packages.db.models.file_remote_location import FileRemoteLocation
    from packages.domain.backup.orchestrator import resolve_backend
    from packages.storage.base import StorageError

    task = _backup_tasks[task_id]
    db = SessionLocal()
    try:
        backend = resolve_backend(db, family_id)
        if backend is None:
            task["status"] = "failed"
            return
        file_ids = [
            f.id for f in db.query(CachedFile).filter(CachedFile.family_id == family_id).all()
        ]
        locations = (
            db.query(FileRemoteLocation)
            .filter(FileRemoteLocation.file_id.in_(file_ids))
            .filter(FileRemoteLocation.sync_status == "synced")
            .all()
        )
        task["files_total"] = len(locations)
        for loc in locations:
            existing = (
                db.query(CachedFile)
                .filter(CachedFile.id == loc.file_id)
                .one_or_none()
            )
            if existing is None:
                task["files_failed"] += 1
                task["failed_files"].append(loc.remote_path)
                continue
            try:
                content = await backend.load(loc.remote_path)
                target = Path(existing.local_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                task["files_completed"] += 1
            except (StorageError, FileNotFoundError, OSError):
                task["files_failed"] += 1
                task["failed_files"].append(loc.remote_path)
        if task["files_failed"] and task["files_completed"]:
            task["status"] = "partial_success"
        elif task["files_failed"]:
            task["status"] = "failed"
        else:
            task["status"] = "completed"
    except Exception:
        logger.exception("文件恢复任务失败: task_id=%s", task_id)
        task["status"] = "failed"
    finally:
        db.close()
