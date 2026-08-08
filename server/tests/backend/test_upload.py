"""Tests for the upload router and StorageService."""
import io
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import StorageBackend

# Minimal valid JPEG magic bytes + padding
JPEG_CONTENT = b"\xff\xd8\xff\xe0" + b"\x00" * 100
# Minimal valid PNG magic bytes
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _upload(client, auth_headers, content: bytes, filename: str = "test.jpg"):
    return client.post(
        "/api/v1/upload/image",
        files={"file": (filename, io.BytesIO(content), "image/jpeg")},
        headers={k: v for k, v in auth_headers.items() if k != "_refresh_token"},
    )


# ---------------------------------------------------------------------------
# Test 1: valid JPEG upload → 200, response has url + file_id, DB row exists
# ---------------------------------------------------------------------------
def test_upload_valid_jpeg(client, auth_headers, db):
    resp = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "url" in data
    assert "file_id" in data
    assert data["filename"] == "test.jpg"
    assert data["size_bytes"] == len(JPEG_CONTENT)

    row = db.query(CachedFile).filter_by(id=data["file_id"]).first()
    assert row is not None
    assert row.size_bytes == len(JPEG_CONTENT)


# ---------------------------------------------------------------------------
# Test 2: upload same content twice → same file_id (dedup)
# ---------------------------------------------------------------------------
def test_upload_dedup(client, auth_headers, db):
    resp1 = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp1.status_code == 200
    file_id_1 = resp1.json()["data"]["file_id"]

    resp2 = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp2.status_code == 200
    file_id_2 = resp2.json()["data"]["file_id"]

    assert file_id_1 == file_id_2
    # Only one DB row
    count = db.query(CachedFile).filter_by(id=file_id_1).count()
    assert count == 1


# ---------------------------------------------------------------------------
# Test 3: file exceeds 5 MB → 400, no DB row
# ---------------------------------------------------------------------------
def test_upload_too_large(client, auth_headers, db):
    big_content = b"\xff\xd8\xff\xe0" + b"\x00" * (5 * 1024 * 1024 + 1)
    resp = _upload(client, auth_headers, big_content)
    assert resp.status_code == 400
    assert db.query(CachedFile).count() == 0


# ---------------------------------------------------------------------------
# Test 4: invalid extension (.gif) → 400, no DB row
# ---------------------------------------------------------------------------
def test_upload_invalid_extension(client, auth_headers, db):
    resp = _upload(client, auth_headers, JPEG_CONTENT, filename="test.gif")
    assert resp.status_code == 400
    assert db.query(CachedFile).count() == 0


# ---------------------------------------------------------------------------
# Test 5: magic bytes mismatch (JPEG ext but PNG content) → 400, no DB row
# ---------------------------------------------------------------------------
def test_upload_magic_bytes_mismatch(client, auth_headers, db):
    resp = _upload(client, auth_headers, PNG_CONTENT, filename="test.jpg")
    assert resp.status_code == 400
    assert db.query(CachedFile).count() == 0


# ---------------------------------------------------------------------------
# Test 6: no default remote backend → FileRemoteLocation absent after upload
# ---------------------------------------------------------------------------
def test_upload_no_remote_backend(client, auth_headers, db):
    resp = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp.status_code == 200
    file_id = resp.json()["data"]["file_id"]
    count = db.query(FileRemoteLocation).filter_by(file_id=file_id).count()
    assert count == 0


# ---------------------------------------------------------------------------
# Test 7: with configured family remote backend → FileRemoteLocation row with sync_status="pending"
# ---------------------------------------------------------------------------
def test_upload_with_remote_backend(client, auth_headers, db):
    # Get the user's family_id via /me
    me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    family_id = me_resp.json()["data"]["family_id"]

    backend = StorageBackend(
        id="test-backend-1",
        family_id=family_id,
        backend_type="local",
        display_name="Test Backend",
        is_active=True,
    )
    db.add(backend)
    db.commit()

    resp = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp.status_code == 200
    file_id = resp.json()["data"]["file_id"]

    loc = db.query(FileRemoteLocation).filter_by(file_id=file_id).first()
    assert loc is not None
    assert loc.sync_status == "pending"
    assert loc.backend_id == backend.id


# ---------------------------------------------------------------------------
# Test 8: concurrent upload race — IntegrityError on INSERT → returns winner's record
# ---------------------------------------------------------------------------
def test_upload_concurrent_race_returns_winner(client, auth_headers, db, tmp_path):
    """Simulate the race: first upload succeeds, second hits IntegrityError on commit.
    The loser should recover gracefully and return the winner's file_id.
    """
    import hashlib
    sha256 = hashlib.sha256(JPEG_CONTENT).hexdigest()

    # Get family_id from auth_headers fixture via a real upload first
    resp_first = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp_first.status_code == 200
    winner_file_id = resp_first.json()["data"]["file_id"]

    # Now simulate a second concurrent upload that hits IntegrityError on commit
    # by patching db.commit to raise IntegrityError once, then succeed
    original_commit = db.commit
    call_count = {"n": 0}

    def patched_commit():
        call_count["n"] += 1
        if call_count["n"] == 1:
            db.rollback()
            raise IntegrityError("UNIQUE constraint failed", {}, None)
        return original_commit()

    with patch.object(db, "commit", side_effect=patched_commit):
        resp_second = _upload(client, auth_headers, JPEG_CONTENT)

    assert resp_second.status_code == 200
    assert resp_second.json()["data"]["file_id"] == str(winner_file_id)
    # Still only one DB row
    assert db.query(CachedFile).filter_by(sha256=sha256).count() == 1
