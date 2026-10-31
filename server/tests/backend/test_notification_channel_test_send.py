"""Tests for send_test_notification's per-channel-type branches."""

from unittest.mock import AsyncMock, patch

import pytest

from apps.backend.app.services.notification.dispatcher import send_test_notification


class _Channel:
    def __init__(self, channel_type: str, family_id: int = 1):
        self.channel_type = channel_type
        self.family_id = family_id
        self.id = 42


@pytest.fixture
def db_stub():
    """Minimal stand-in for the Session used by send_test_notification."""

    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class _DB:
        def __init__(self, push_subs):
            self._push_subs = push_subs
            self.deleted = []

        def query(self, model):
            name = getattr(model, "__name__", "")
            if name == "PushSubscription":
                return _Query(self._push_subs)
            return _Query([])

        def delete(self, obj):
            self.deleted.append(obj)

        def commit(self):
            pass

    return _DB


@pytest.fixture(autouse=True)
def _stub_locale():
    with patch(
        "apps.backend.app.services.notification.dispatcher._resolve_locale",
        return_value="zh-CN",
    ), patch(
        "apps.backend.app.services.notification.dispatcher._env_prefix",
        return_value="",
    ):
        yield


async def test_telegram_missing_credentials():
    ok, err = await send_test_notification(
        db=None, channel=_Channel("telegram"), config={"bot_token": ""}
    )
    assert ok is False
    assert "bot_token" in err


async def test_telegram_success():
    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_telegram",
        new=AsyncMock(return_value=True),
    ) as send:
        ok, err = await send_test_notification(
            db=None,
            channel=_Channel("telegram"),
            config={"bot_token": "t", "chat_id": "1"},
        )
    assert (ok, err) == (True, None)
    send.assert_awaited_once()


async def test_telegram_failure_surfaces_reason():
    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_telegram",
        new=AsyncMock(return_value=False),
    ):
        ok, err = await send_test_notification(
            db=None,
            channel=_Channel("telegram"),
            config={"bot_token": "t", "chat_id": "1"},
        )
    assert ok is False
    assert err


async def test_feishu_missing_webhook():
    ok, err = await send_test_notification(
        db=None, channel=_Channel("feishu"), config={"webhook_url": ""}
    )
    assert ok is False
    assert "webhook_url" in err


async def test_email_invalid_port():
    ok, err = await send_test_notification(
        db=None,
        channel=_Channel("email"),
        config={"smtp_host": "smtp.example.com", "smtp_port": "not-a-port"},
    )
    assert ok is False
    assert "SMTP" in err


async def test_webpush_without_subscriptions(db_stub):
    db = db_stub([])
    ok, err = await send_test_notification(
        db=db, channel=_Channel("webpush"), config={"vapid_private_key": "k"}
    )
    assert ok is False
    assert "推送订阅" in err


async def test_webpush_prunes_gone_subscription_and_reports_success(db_stub):
    """One 410 sub is deleted; a successful sibling makes the test pass."""
    gone = type("Sub", (), {"endpoint": "https://gone", "p256dh": "p", "auth": "a"})()
    live = type("Sub", (), {"endpoint": "https://live", "p256dh": "p", "auth": "a"})()
    db = db_stub([gone, live])

    results = iter(["gone", True])

    def fake_send(*a, **k):
        return next(results)

    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_webpush",
        side_effect=fake_send,
    ):
        ok, err = await send_test_notification(
            db=db, channel=_Channel("webpush"), config={"vapid_private_key": "k"}
        )

    assert (ok, err) == (True, None)
    assert db.deleted == [gone]


async def test_webpush_all_failed(db_stub):
    sub = type("Sub", (), {"endpoint": "https://x", "p256dh": "p", "auth": "a"})()
    db = db_stub([sub])
    with patch(
        "apps.backend.app.services.notification.dispatcher.NotificationSender.send_webpush",
        return_value=False,
    ):
        ok, err = await send_test_notification(
            db=db, channel=_Channel("webpush"), config={"vapid_private_key": "k"}
        )
    assert ok is False
    assert "推送订阅" in err


async def test_unsupported_channel_type():
    ok, err = await send_test_notification(
        db=None, channel=_Channel("carrier_pigeon"), config={}
    )
    assert ok is False
    assert "carrier_pigeon" in err
