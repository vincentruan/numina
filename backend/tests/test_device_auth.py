from app.models.device_session import DeviceSession


def test_device_session_model_exists(db):
    """DeviceSession table is created and can be queried."""
    count = db.query(DeviceSession).count()
    assert count == 0
