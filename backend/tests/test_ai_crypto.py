from app.services.ai_crypto import mask_api_key


def test_mask_api_key_empty():
    assert mask_api_key("") == "****"


def test_mask_api_key_short():
    # len <= 14 → "****"
    assert mask_api_key("sk-short") == "****"
    assert mask_api_key("a" * 14) == "****"


def test_mask_api_key_boundary():
    # len == 15 → first 6 + ******** + last 4
    key = "abcdefghijklmno"  # 15 chars: prefix=abcdef, suffix=lmno
    assert mask_api_key(key) == "abcdef********lmno"


def test_mask_api_key_typical():
    key = "sk-abc123def456ghi789"  # 21 chars: prefix=sk-abc, suffix=i789
    assert mask_api_key(key) == "sk-abc********i789"


def test_mask_api_key_exact_10():
    assert mask_api_key("a" * 10) == "****"


def test_mask_api_key_exact_14():
    assert mask_api_key("a" * 14) == "****"


def test_mask_api_key_long():
    key = "sk-" + "x" * 50
    result = mask_api_key(key)
    assert result.startswith("sk-xxx")
    assert "********" in result
    assert result.endswith("xxxx")
