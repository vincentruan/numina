# backend/app/services/notification/dispatcher.py
import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.notification_channel import NotificationChannel
from apps.backend.app.models.notification_channel_config import (
    NotificationChannelConfig,
)
from apps.backend.app.models.notification_config import NotificationConfig
from apps.backend.app.models.notification_subscription import NotificationSubscription
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.models.reminder_notification import ReminderNotification
from apps.backend.app.schemas.reminder import ReminderSummary
from apps.backend.app.services.notification.rules import (
    check_expiring_soon,
    check_large_purchase,
    check_maturity,
)
from apps.backend.app.services.notification.sender import (
    NotificationSender,
    render_template,
)
from apps.backend.app.services.storage.config_crypto import decrypt_config
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


def ensure_reminder(db: Session, data: dict) -> Reminder | None:
    """幂等创建 reminder：同 family_id + reminder_type + asset_id + status=active 已存在则跳过。"""
    existing = (
        db.query(Reminder)
        .filter_by(
            family_id=data["family_id"],
            reminder_type=data["reminder_type"],
            asset_id=data.get("asset_id"),
            status="active",
        )
        .first()
    )
    if existing:
        return None
    reminder = Reminder(
        id=next_id(),
        family_id=data["family_id"],
        reminder_type=data["reminder_type"],
        title=data["title"],
        body=data["body"],
        severity=data["severity"],
        asset_id=data.get("asset_id"),
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    _dispatch_notifications(db, reminder, data.get("template_vars", {}))
    return reminder


def get_reminder_summary(db: Session, family_id: int) -> ReminderSummary:
    rows = (
        db.query(Reminder.reminder_type)
        .filter_by(family_id=family_id, status="active")
        .all()
    )
    counts: dict[str, int] = {}
    for (rtype,) in rows:
        counts[rtype] = counts.get(rtype, 0) + 1
    return ReminderSummary(
        large_purchase=counts.get("large_purchase", 0),
        expiring_soon=counts.get("expiring_soon", 0),
        maturity=counts.get("maturity", 0),
        total=sum(counts.values()),
    )


def check_on_asset_write(db: Session, asset: Asset) -> None:
    """资产写入时实时检测大额消费冷静期。"""
    if not asset.purchase_price:
        return
    config = db.query(NotificationConfig).filter_by(family_id=asset.family_id).first()
    if config is None:
        return
    if (
        config.large_purchase_threshold_fixed is None
        and config.large_purchase_threshold_multiplier is None
    ):
        return

    avg_monthly = _calc_avg_monthly_spend(db, asset.family_id)
    result = check_large_purchase(
        db=db,
        family_id=asset.family_id,
        asset_id=asset.id,
        asset_name=asset.name,
        purchase_price=float(asset.purchase_price),
        threshold_fixed=config.large_purchase_threshold_fixed,
        threshold_multiplier=config.large_purchase_threshold_multiplier,
        avg_monthly_spend=avg_monthly,
    )
    if result:
        ensure_reminder(db, result)


def run_scheduled_checks(db: Session) -> None:
    """APScheduler 每日 09:20 调用：检测到期类 + 清理过期冷静期 + 重试失败推送。"""
    _resolve_expired_large_purchase(db)
    _check_expiring_assets(db)
    _check_maturity_assets(db)
    _retry_failed_notifications(db)


# ── 内部辅助 ──────────────────────────────────────────────────────────────────


def _calc_avg_monthly_spend(db: Session, family_id: int) -> float | None:
    cutoff = date.today() - timedelta(days=90)
    result = (
        db.query(func.sum(Asset.purchase_price))
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date >= cutoff,
        )
        .scalar()
    )
    if result is None:
        return None
    return float(result) / 3.0


def _resolve_expired_large_purchase(db: Session) -> None:
    cutoff = datetime.now() - timedelta(hours=48)
    db.query(Reminder).filter(
        Reminder.reminder_type == "large_purchase",
        Reminder.status == "active",
        Reminder.created_at <= cutoff,
    ).update({"status": "resolved", "resolved_at": datetime.now()})
    db.commit()


def _check_expiring_assets(db: Session) -> None:
    assets = (
        db.query(Asset)
        .filter(Asset.is_archived.is_(False), Asset.warranty_expiry_date.isnot(None))
        .all()
    )
    for asset in assets:
        if asset.warranty_expiry_date is None:
            continue
        result = check_expiring_soon(
            family_id=asset.family_id,
            asset_id=asset.id,
            asset_name=asset.name,
            expiry_date=asset.warranty_expiry_date,
        )
        if result:
            ensure_reminder(db, result)


def _check_maturity_assets(db: Session) -> None:
    assets = (
        db.query(Asset)
        .filter(Asset.is_archived.is_(False), Asset.maturity_date.isnot(None))
        .all()
    )
    for asset in assets:
        if asset.maturity_date is None:
            continue
        result = check_maturity(
            family_id=asset.family_id,
            asset_id=asset.id,
            asset_name=asset.name,
            maturity_date=asset.maturity_date,
            amount=float(asset.current_value)
            if asset.current_value is not None
            else None,
        )
        if result:
            ensure_reminder(db, result)


def _get_channel_config(db: Session, channel: NotificationChannel) -> dict:
    """Read channel config from NotificationChannelConfig table."""
    rows = db.query(NotificationChannelConfig).filter_by(channel_id=channel.id).all()
    result = {}
    for row in rows:
        try:
            decrypted = decrypt_config(row.value_encrypted)
            if decrypted and isinstance(decrypted, dict):
                result.update(decrypted)
            else:
                result[row.key] = row.value_encrypted
        except Exception:
            result[row.key] = row.value_encrypted
    return result


def _dispatch_notifications(
    db: Session, reminder: Reminder, template_vars: dict
) -> None:
    """向订阅了该 reminder_type 的所有启用渠道发送通知（失败静默）。"""
    channels = (
        db.query(NotificationChannel)
        .join(
            NotificationSubscription,
            NotificationChannel.id == NotificationSubscription.channel_id,
        )
        .filter(
            NotificationChannel.family_id == reminder.family_id,
            NotificationChannel.is_enabled,
            NotificationSubscription.reminder_type == reminder.reminder_type,
        )
        .all()
    )
    already_sent = {
        rn.channel_id
        for rn in db.query(ReminderNotification)
        .filter_by(reminder_id=reminder.id, status="sent")
        .all()
    }
    for channel in channels:
        if channel.id in already_sent:
            continue
        config = _get_channel_config(db, channel)
        if channel.channel_type == "telegram":
            # Telegram is async — ReminderNotification is written inside
            # _send_telegram_async once the actual result is known.
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    _send_telegram_async(channel, reminder, template_vars, db)
                )
            except RuntimeError:
                pass
        elif channel.channel_type == "email":
            subject = render_template(
                reminder.reminder_type, "email_subject", template_vars
            )
            body = render_template(reminder.reminder_type, "email_body", template_vars)
            success = NotificationSender.send_email(
                smtp_host=config.get("smtp_host", ""),
                smtp_port=int(config.get("smtp_port", 587)),
                smtp_user=config.get("smtp_user", ""),
                smtp_password=config.get("smtp_password", ""),
                smtp_from=config.get("smtp_from", ""),
                to=config.get("to", ""),
                subject=subject,
                body=body,
            )
            rn = ReminderNotification(
                reminder_id=reminder.id,
                channel_id=channel.id,
                status="sent" if success else "failed",
            )
            db.add(rn)
    db.commit()


async def _send_telegram_async(
    channel: NotificationChannel,
    reminder: Reminder,
    template_vars: dict,
    db: Session,
) -> None:
    config = _get_channel_config(db, channel)
    text = render_template(reminder.reminder_type, "telegram", template_vars)
    success = await NotificationSender.send_telegram(
        bot_token=config.get("bot_token", ""),
        chat_id=config.get("chat_id", ""),
        text=text,
    )
    rn = ReminderNotification(
        reminder_id=reminder.id,
        channel_id=channel.id,
        status="sent" if success else "failed",
    )
    db.add(rn)
    db.commit()


def _retry_failed_notifications(db: Session) -> None:
    """重试尚未推送成功且重试次数 < 3 的 active reminders。"""
    MAX_RETRIES = 3
    pending = db.query(Reminder).filter(Reminder.status == "active").all()
    for reminder in pending:
        # 查新表：已成功通知的渠道
        sent_channel_ids = {
            rn.channel_id
            for rn in db.query(ReminderNotification)
            .filter_by(reminder_id=reminder.id, status="sent")
            .all()
        }
        # 查新表：失败次数
        retry_count = (
            db.query(ReminderNotification)
            .filter_by(reminder_id=reminder.id, status="failed")
            .count()
        )
        if retry_count >= MAX_RETRIES:
            logger.info("提醒 %s 已达最大重试次数，放弃推送", reminder.id)
            continue
        channels = (
            db.query(NotificationChannel)
            .join(
                NotificationSubscription,
                NotificationChannel.id == NotificationSubscription.channel_id,
            )
            .filter(
                NotificationChannel.family_id == reminder.family_id,
                NotificationChannel.is_enabled,
                NotificationSubscription.reminder_type == reminder.reminder_type,
            )
            .all()
        )
        if not channels:
            continue
        all_notified = all(c.id in sent_channel_ids for c in channels)
        if all_notified:
            continue
        _dispatch_notifications(db, reminder, {})
