# backend/app/services/notification/dispatcher.py
import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.notification_channel import NotificationChannel
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
    _format_mention,
    render_template,
)
from apps.backend.app.services.storage.config_crypto import decrypt_config
from apps.backend.app.utils.snowflake import next_id
from packages.core.settings import settings
from packages.db.models.notification_channel_config import (
    NotificationChannelConfig,
)
from packages.db.models.notification_config import NotificationConfig
from packages.db.models.push_subscription import PushSubscription

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


def _check_reminder_dedup(
    db: Session, family_id: int, reminder_type: str, title: str, hours: int = 1
) -> bool:
    """Check if a similar reminder was created recently (deduplication)."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    existing = (
        db.query(Reminder)
        .filter(
            Reminder.family_id == family_id,
            Reminder.reminder_type == reminder_type,
            Reminder.title == title,
            Reminder.created_at >= cutoff,
        )
        .first()
    )
    return existing is not None


def notify_ai_task_complete(
    db: Session, family_id: int, task_type: str, task_title: str
) -> None:
    """Create a Reminder for AI task completion and dispatch.

    Includes deduplication: skips if same task_type+title was notified within 1 hour.
    """
    reminder_type = f"ai_{task_type}_complete"
    title = f"AI 任务完成：{task_title}"

    if _check_reminder_dedup(db, family_id, reminder_type, title, hours=1):
        return

    template_vars = {"task_title": task_title}
    body = f"「{task_title}」已生成完成，点击查看。"

    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": reminder_type,
            "title": title,
            "body": body,
            "severity": "info",
            "template_vars": template_vars,
        },
    )


def notify_chore_completed(
    db: Session, family_id: int, child_name: str, chore_title: str
) -> None:
    """Create a Reminder for chore completion and dispatch."""
    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": "chore_completed",
            "title": f"儿童任务完成：{chore_title}",
            "body": f"{child_name} 完成了任务「{chore_title}」，快去看看吧！",
            "severity": "info",
            "template_vars": {"child_name": child_name, "chore_title": chore_title},
        },
    )


def notify_treasure_redeemed(
    db: Session, family_id: int, child_name: str, treasure_title: str
) -> None:
    """Create a Reminder for treasure redemption and dispatch."""
    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": "treasure_redeemed",
            "title": f"宝贝兑换：{treasure_title}",
            "body": f"{child_name} 兑换了宝贝「{treasure_title}」！",
            "severity": "info",
            "template_vars": {
                "child_name": child_name,
                "treasure_title": treasure_title,
            },
        },
    )


def notify_wish_redeemed(
    db: Session, family_id: int, wish_title: str, child_name: str
) -> None:
    """Create a Reminder for wish redemption and dispatch."""
    ensure_reminder(
        db,
        {
            "family_id": family_id,
            "reminder_type": "wish_redeemed",
            "title": f"心愿兑现：{wish_title}",
            "body": f"{child_name} 的心愿「{wish_title}」已兑现！",
            "severity": "info",
            "template_vars": {"child_name": child_name, "wish_title": wish_title},
        },
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


# ── 环境前缀 ────────────────────────────────────────────────────────────────────


def _env_prefix() -> str:
    """非生产环境时返回消息前缀，避免用户与生产混淆。"""
    if settings.ENVIRONMENT != "production":
        return "【测试】"
    return ""


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
    cutoff = datetime.now(UTC) - timedelta(hours=48)
    db.query(Reminder).filter(
        Reminder.reminder_type == "large_purchase",
        Reminder.status == "active",
        Reminder.created_at <= cutoff,
    ).update({"status": "resolved", "resolved_at": datetime.now(UTC)})
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
            prefix = _env_prefix()
            if prefix:
                subject = f"{prefix} {subject}"
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
        elif channel.channel_type == "feishu":
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    _send_feishu_async(channel, reminder, template_vars, db)
                )
            except RuntimeError:
                pass
        elif channel.channel_type == "webpush":
            _send_webpush_sync(channel, reminder, template_vars, db)
    db.commit()


async def _send_feishu_async(
    channel: NotificationChannel,
    reminder: Reminder,
    template_vars: dict,
    db: Session,
) -> None:
    config = _get_channel_config(db, channel)
    text = render_template(reminder.reminder_type, "feishu", template_vars)
    prefix = _env_prefix()
    if prefix:
        text = f"{prefix}\n\n{text}"
    mention_config = config.get("mention_config")
    if mention_config:
        text = _format_mention(text, "feishu", mention_config)
    success = await NotificationSender.send_feishu(
        webhook_url=config.get("webhook_url", ""),
        secret=config.get("secret", ""),
        text=text,
    )
    rn = ReminderNotification(
        reminder_id=reminder.id,
        channel_id=channel.id,
        status="sent" if success else "failed",
    )
    db.add(rn)
    db.commit()


def _send_webpush_sync(
    channel: NotificationChannel,
    reminder: Reminder,
    template_vars: dict,
    db: Session,
) -> None:
    """Send Web Push notifications to all subscriptions in the family."""
    # R11 (large_purchase) should only notify main app subscriptions, not child
    if reminder.reminder_type == "large_purchase":
        subscriptions = (
            db.query(PushSubscription)
            .filter(
                PushSubscription.family_id == reminder.family_id,
                PushSubscription.app_type == "main",
            )
            .all()
        )
    else:
        subscriptions = (
            db.query(PushSubscription)
            .filter(PushSubscription.family_id == reminder.family_id)
            .all()
        )
    if not subscriptions:
        return

    config = _get_channel_config(db, channel)
    vapid_private_key = config.get("vapid_private_key", settings.VAPID_PRIVATE_KEY)
    vapid_claims = {"sub": settings.VAPID_SUBJECT}

    title = render_template(reminder.reminder_type, "webpush_title", template_vars)
    body = render_template(reminder.reminder_type, "webpush_body", template_vars)
    prefix = _env_prefix()
    if prefix:
        title = f"{prefix} {title}"

    any_success = False
    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        notification_data = {
            "title": title,
            "body": body,
            "reminder_type": reminder.reminder_type,
            "reminder_id": str(reminder.id),
        }
        result = NotificationSender.send_webpush(
            subscription_info, notification_data, vapid_private_key, vapid_claims
        )
        if result == "gone":
            db.delete(sub)
        else:
            if result:
                any_success = True

    rn = ReminderNotification(
        reminder_id=reminder.id,
        channel_id=channel.id,
        status="sent" if any_success else "failed",
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
    prefix = _env_prefix()
    if prefix:
        text = f"{prefix}\n\n{text}"
    mention_config = config.get("mention_config")
    if mention_config:
        text = _format_mention(text, "telegram", mention_config)
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


async def _dispatch_digest(db: Session, channel: NotificationChannel) -> None:
    """Send digest notification for pending reminders.

    Collects all active reminders that haven't been sent to this channel yet
    and sends them as a single batched message.
    """
    config = _get_channel_config(db, channel)

    # Find all active reminders for this family that haven't been sent to this channel
    sent_reminder_ids = {
        rn.reminder_id
        for rn in db.query(ReminderNotification)
        .filter_by(channel_id=channel.id, status="sent")
        .all()
    }

    pending_reminders = (
        db.query(Reminder)
        .filter(
            Reminder.family_id == channel.family_id,
            Reminder.status == "active",
            ~Reminder.id.in_(sent_reminder_ids),
        )
        .all()
    )

    if not pending_reminders:
        return

    # Build digest message
    lines = [f"📬 您有 {len(pending_reminders)} 条待处理提醒：\n"]
    for i, reminder in enumerate(pending_reminders, 1):
        lines.append(f"{i}. {reminder.title}")
        if reminder.body:
            lines.append(f"   {reminder.body}")
        lines.append("")

    digest_text = "\n".join(lines).rstrip()

    # Apply mention formatting if configured
    mention_config = config.get("mention_config")
    if mention_config:
        digest_text = _format_mention(digest_text, channel.channel_type, mention_config)

    # Send via appropriate channel
    success = False
    if channel.channel_type == "telegram":
        success = await NotificationSender.send_telegram(
            bot_token=config.get("bot_token", ""),
            chat_id=config.get("chat_id", ""),
            text=digest_text,
        )
    elif channel.channel_type == "feishu":
        success = await NotificationSender.send_feishu(
            webhook_url=config.get("webhook_url", ""),
            secret=config.get("secret", ""),
            text=digest_text,
        )

    # Mark all pending reminders as sent to this channel
    for reminder in pending_reminders:
        rn = ReminderNotification(
            reminder_id=reminder.id,
            channel_id=channel.id,
            status="sent" if success else "failed",
        )
        db.add(rn)

    # Update digest_sent_at for all pending reminders
    if success:
        now = datetime.now(UTC)
        for reminder in pending_reminders:
            reminder.digest_sent_at = now

    db.commit()
