from apps.backend.app.services.ai_crypto import mask_api_key


def test_mask_api_key_empty():
    assert mask_api_key("") == "****"


def test_mask_api_key_short():
    # len <= 11 → "****"
    assert mask_api_key("sk-short") == "****"
    assert mask_api_key("a" * 11) == "****"


def test_mask_api_key_boundary():
    # len == 12 → first 7 + * + last 4
    key = "abcdefghijkl"  # 12 chars: prefix=abcdefg, suffix=ijkl, hidden=1
    assert mask_api_key(key) == "abcdefg*ijkl"


def test_mask_api_key_typical():
    key = "sk-abc123def456ghi789"  # 21 chars: prefix=sk-abc1, suffix=i789, hidden=10
    assert mask_api_key(key) == "sk-abc1**********i789"


def test_mask_api_key_exact_10():
    assert mask_api_key("a" * 10) == "****"


def test_mask_api_key_exact_14():
    # len 14 > 11 → masked: prefix=7, suffix=4, hidden=3
    assert mask_api_key("a" * 14) == "aaaaaaa***aaaa"


def test_mask_api_key_long():
    key = "sk-" + "x" * 50
    result = mask_api_key(key)
    assert result.startswith("sk-xxxx")
    assert "********" in result
    assert result.endswith("xxxx")
