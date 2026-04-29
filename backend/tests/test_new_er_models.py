from datetime import date

from app.models.asset_lifecycle_event import AssetLifecycleEvent
from app.models.child_economy_config import ChildEconomyConfig
from app.models.child_wish_cost_history import ChildWishCostHistory
from app.models.notification_channel_config import NotificationChannelConfig
from app.models.reminder_notification import ReminderNotification
from app.utils.snowflake import next_id


def test_child_economy_config(db):
    cfg = ChildEconomyConfig(family_id=next_id())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    assert cfg.id is not None
    assert cfg.auto_approve_hours == 24
    assert cfg.coin_copper_to_silver == 10
    assert cfg.coin_silver_to_gold == 10


def test_asset_lifecycle_event(db):
    evt = AssetLifecycleEvent(
        asset_id=next_id(),
        event_type="sold",
        event_date=date.today(),
        sell_price=1000.0,
        sell_fee=50.0,
        sell_channel="闲鱼",
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    assert evt.id is not None
    assert evt.event_type == "sold"


def test_asset_lifecycle_event_retired(db):
    evt = AssetLifecycleEvent(
        asset_id=next_id(),
        event_type="retired",
        event_date=date.today(),
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    assert evt.event_type == "retired"
    assert evt.sell_price is None
    assert evt.sell_channel is None


def test_reminder_notification(db):
    rn = ReminderNotification(
        reminder_id=next_id(),
        channel_id=next_id(),
        status="sent",
    )
    db.add(rn)
    db.commit()
    db.refresh(rn)
    assert rn.status == "sent"


def test_child_wish_cost_history(db):
    h = ChildWishCostHistory(
        wish_id=next_id(),
        old_cost=100,
        new_cost=80,
        changed_by_user_id=next_id(),
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    assert h.old_cost == 100
    assert h.new_cost == 80


def test_notification_channel_config(db):
    c = NotificationChannelConfig(
        channel_id=next_id(),
        key="bot_token",
        value_encrypted="enc_token",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.key == "bot_token"
    assert c.value_encrypted == "enc_token"
