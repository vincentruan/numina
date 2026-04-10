"""Tests for the upload router and StorageService."""
import io

import pytest

from app.models.cached_file import CachedFile
from app.models.file_remote_location import FileRemoteLocation
from app.models.storage_backend import StorageBackend

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
    data = resp.json()
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
    file_id_1 = resp1.json()["file_id"]

    resp2 = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp2.status_code == 200
    file_id_2 = resp2.json()["file_id"]

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
    file_id = resp.json()["file_id"]
    count = db.query(FileRemoteLocation).filter_by(file_id=file_id).count()
    assert count == 0


# ---------------------------------------------------------------------------
# Test 7: with default remote backend → FileRemoteLocation row with sync_status="pending"
# ---------------------------------------------------------------------------
def test_upload_with_remote_backend(client, auth_headers, db):
    backend = StorageBackend(
        id="test-backend-1",
        backend_type="local",
        display_name="Test Backend",
        is_default=True,
        is_active=True,
    )
    db.add(backend)
    db.commit()

    resp = _upload(client, auth_headers, JPEG_CONTENT)
    assert resp.status_code == 200
    file_id = resp.json()["file_id"]

    loc = db.query(FileRemoteLocation).filter_by(file_id=file_id).first()
    assert loc is not None
    assert loc.sync_status == "pending"
    assert loc.backend_id == "test-backend-1"
