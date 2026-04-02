"""File upload security validation using magic bytes."""

from typing import Optional

# Magic bytes for allowed image formats
MAGIC_BYTES = {
    # JPEG: starts with FF D8 FF
    "jpeg": bytes([0xFF, 0xD8, 0xFF]),
    "jpg": bytes([0xFF, 0xD8, 0xFF]),
    # PNG: starts with 89 50 4E 47 0D 0A 1A 0A
    "png": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    # WebP: starts with 52 49 46 46 (RIFF)
    "webp": bytes([0x52, 0x49, 0x46, 0x46]),
}

# WebP marker at offset 8-11
WEBP_MARKER = bytes([0x57, 0x45, 0x42, 0x50])  # "WEBP"


def validate_image_magic_bytes(content: bytes, extension: str) -> bool:
    """Validate file content matches expected image format by magic bytes.

    Args:
        content: Raw file bytes (first 12 bytes minimum)
        extension: File extension without dot (e.g., "jpg", "png", "webp")

    Returns:
        True if magic bytes match expected format, False otherwise.
    """
    ext = extension.lower()

    if ext in ("jpg", "jpeg"):
        return len(content) >= 3 and content[:3] == MAGIC_BYTES["jpeg"]

    if ext == "png":
        return len(content) >= 8 and content[:8] == MAGIC_BYTES["png"]

    if ext == "webp":
        # WebP: RIFF....WEBP
        if len(content) < 12:
            return False
        return content[:4] == MAGIC_BYTES["webp"] and content[8:12] == WEBP_MARKER

    return False


def detect_image_format(content: bytes) -> Optional[str]:
    """Detect image format from magic bytes regardless of extension.

    Args:
        content: Raw file bytes (at least 12 bytes)

    Returns:
        Detected format ("jpg", "png", "webp") or None if unrecognized.
    """
    if len(content) < 12:
        return None

    if content[:3] == MAGIC_BYTES["jpeg"]:
        return "jpg"

    if content[:8] == MAGIC_BYTES["png"]:
        return "png"

    if content[:4] == MAGIC_BYTES["webp"] and content[8:12] == WEBP_MARKER:
        return "webp"

    return None