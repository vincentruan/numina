"""Tests for file validation service."""


from app.services.file_validation import detect_image_format, validate_image_magic_bytes


class TestValidateImageMagicBytes:
    """Tests for validate_image_magic_bytes function."""

    def test_validate_jpeg(self):
        """Test JPEG magic bytes validation."""
        # Valid JPEG header
        valid_jpeg = bytes([0xFF, 0xD8, 0xFF, 0x00, 0x00, 0x00])
        assert validate_image_magic_bytes(valid_jpeg, "jpg") is True
        assert validate_image_magic_bytes(valid_jpeg, "jpeg") is True

    def test_validate_png(self):
        """Test PNG magic bytes validation."""
        # Valid PNG header
        valid_png = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        assert validate_image_magic_bytes(valid_png, "png") is True

    def test_validate_webp(self):
        """Test WebP magic bytes validation."""
        # Valid WebP: RIFF + size + WEBP
        valid_webp = bytes([
            0x52, 0x49, 0x46, 0x46,  # RIFF
            0x00, 0x00, 0x00, 0x00,  # dummy size
            0x57, 0x45, 0x42, 0x50,  # WEBP
        ])
        assert validate_image_magic_bytes(valid_webp, "webp") is True

    def test_reject_fake_jpeg(self):
        """Test rejection of fake JPEG (PNG header with .jpg extension)."""
        fake_jpeg = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG header
        assert validate_image_magic_bytes(fake_jpeg, "jpg") is False

    def test_reject_fake_png(self):
        """Test rejection of fake PNG (JPEG header with .png extension)."""
        fake_png = bytes([0xFF, 0xD8, 0xFF])
        assert validate_image_magic_bytes(fake_png, "png") is False

    def test_reject_fake_webp(self):
        """Test rejection of fake WebP."""
        fake_webp = bytes([0xFF, 0xD8, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert validate_image_magic_bytes(fake_webp, "webp") is False

    def test_reject_too_short_content(self):
        """Test rejection of content that's too short."""
        short_content = bytes([0xFF])
        assert validate_image_magic_bytes(short_content, "jpg") is False

    def test_reject_unknown_extension(self):
        """Test rejection of unknown extension."""
        content = bytes([0xFF, 0xD8, 0xFF])
        assert validate_image_magic_bytes(content, "gif") is False


class TestDetectImageFormat:
    """Tests for detect_image_format function."""

    def test_detect_jpeg(self):
        """Test detecting JPEG format."""
        # Need at least 12 bytes
        jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert detect_image_format(jpeg_bytes) == "jpg"

    def test_detect_png(self):
        """Test detecting PNG format."""
        # Need at least 12 bytes
        png_bytes = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x00])
        assert detect_image_format(png_bytes) == "png"

    def test_detect_webp(self):
        """Test detecting WebP format."""
        webp_bytes = bytes([0x52, 0x49, 0x46, 0x46, 0x00, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50])
        assert detect_image_format(webp_bytes) == "webp"

    def test_detect_unknown_format(self):
        """Test detecting unknown format."""
        unknown_bytes = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert detect_image_format(unknown_bytes) is None

    def test_detect_too_short_content(self):
        """Test detecting with content too short."""
        short_bytes = bytes([0xFF, 0xD8])
        assert detect_image_format(short_bytes) is None