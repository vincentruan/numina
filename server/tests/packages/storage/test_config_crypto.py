"""Tests for packages.storage.config_crypto — 配置加解密。

密钥来源（见 config_crypto._fernet_key）：
- 若 settings.STORAGE_ENCRYPTION_KEY 非空，直接用作 Fernet key；
- 否则用 SECRET_KEY 的 SHA256 派生 Fernet key（并打 warning）。

测试通过 monkeypatch settings.STORAGE_ENCRYPTION_KEY 保证确定性。
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from cryptography.fernet import Fernet

from packages.core.settings import settings
from packages.storage import config_crypto as cc


@pytest.fixture()
def fernet_key(monkeypatch):
    """设置一个确定的 STORAGE_ENCRYPTION_KEY 并返回它。"""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "STORAGE_ENCRYPTION_KEY", key)
    return key


@pytest.fixture()
def derived_key(monkeypatch):
    """清空 STORAGE_ENCRYPTION_KEY，走 SECRET_KEY 派生路径，返回期望的派生 key。"""
    monkeypatch.setattr(settings, "STORAGE_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-for-derivation")
    return base64.urlsafe_b64encode(hashlib.sha256(b"test-secret-key-for-derivation").digest())


class TestFernetKey:
    def test_uses_storage_key_when_set(self, fernet_key):
        assert cc._fernet_key() == fernet_key.encode()

    def test_derives_from_secret_key_when_unset(self, derived_key):
        assert cc._fernet_key() == derived_key


class TestRoundTrip:
    def test_encrypt_decrypt_roundtrip(self, fernet_key):
        config = {"token": "abc123", "repo": "owner/repo", "branch": "main", "n": 42}
        ciphertext = cc.encrypt_config(config)
        assert isinstance(ciphertext, str)
        # 密文不应包含明文 token
        assert "abc123" not in ciphertext
        assert cc.decrypt_config(ciphertext) == config

    def test_roundtrip_with_derived_key(self, derived_key):
        config = {"url": "https://dav.example.com", "username": "u"}
        assert cc.decrypt_config(cc.encrypt_config(config)) == config

    def test_encrypt_produces_valid_fernet_token(self, fernet_key):
        # 用同一把 key 直接解密，验证 encrypt_config 产物的格式
        ciphertext = cc.encrypt_config({"k": "v"})
        f = Fernet(fernet_key.encode())
        assert json.loads(f.decrypt(ciphertext.encode())) == {"k": "v"}

    def test_roundtrip_nested_and_unicode(self, fernet_key):
        config = {"nested": {"a": [1, 2, 3]}, "name": "家庭网盘"}
        assert cc.decrypt_config(cc.encrypt_config(config)) == config


class TestDecryptPlaintext:
    """decrypt_config 对明文 JSON 输入的兼容分支。"""

    def test_plaintext_json_dict_passthrough(self):
        # 已是 dict 的 JSON 字符串直接返回（无需密钥）
        assert cc.decrypt_config('{"k": 2, "s": "x"}') == {"k": 2, "s": "x"}

    def test_json_string_wrapping_ciphertext(self, fernet_key):
        # JSON 字符串内容本身是密文：先 json.loads 得到 str，再按密文解密
        ciphertext = cc.encrypt_config({"a": 1})
        wrapped = json.dumps(ciphertext)  # 带引号的 JSON 字符串
        assert cc.decrypt_config(wrapped) == {"a": 1}


class TestDecryptFailures:
    """decrypt_config 在失败时返回 None（不抛异常）。"""

    def test_none_returns_none(self):
        assert cc.decrypt_config(None) is None

    def test_empty_string_returns_none(self):
        assert cc.decrypt_config("") is None

    def test_tampered_ciphertext_returns_none(self, fernet_key):
        ciphertext = cc.encrypt_config({"a": 1})
        tampered = ciphertext[:-4] + "AAAA"
        assert cc.decrypt_config(tampered) is None

    def test_garbage_returns_none(self, fernet_key):
        assert cc.decrypt_config("not-json-not-fernet!!!") is None

    def test_wrong_key_returns_none(self, fernet_key):
        # 用另一把 key 加密的密文，当前 key 解不开 → None
        other = Fernet(Fernet.generate_key())
        other_ct = other.encrypt(json.dumps({"x": 9}).encode()).decode()
        assert cc.decrypt_config(other_ct) is None

    def test_key_rotation_breaks_old_ciphertext(self, monkeypatch):
        # key1 加密 → 换成 key2 后解密失败返回 None
        monkeypatch.setattr(settings, "STORAGE_ENCRYPTION_KEY", Fernet.generate_key().decode())
        ciphertext = cc.encrypt_config({"a": 1})
        monkeypatch.setattr(settings, "STORAGE_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert cc.decrypt_config(ciphertext) is None
