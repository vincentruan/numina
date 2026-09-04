"""Tests for packages.security.service_auth.agent_jwt — backend→agent 服务间 JWT.

create_agent_token 是纯 JWT 编码, 无需数据库; 用 settings.SECRET_KEY 解码验证 payload.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from packages.core.settings import settings
from packages.security.service_auth.agent_jwt import (
    _AGENT_TOKEN_TTL_SECONDS,
    ALGORITHM,
    create_agent_token,
)


def _decode(token: str) -> dict:
    """用与签发相同的密钥/算法解码 (验签)."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def test_create_agent_token_payload_fields():
    """payload 应包含 sub/fid/agt/iat/exp/type 且值正确."""
    token = create_agent_token(family_id="fam-123", agent_instance_id="backend")
    payload = _decode(token)

    assert payload["sub"] == "agent"
    assert payload["fid"] == "fam-123"
    assert payload["agt"] == "backend"
    assert payload["type"] == "agent"
    assert "iat" in payload
    assert "exp" in payload


def test_create_agent_token_default_agent_instance_id():
    """agent_instance_id 默认值为 'backend'."""
    payload = _decode(create_agent_token(family_id="fam-x"))
    assert payload["agt"] == "backend"


def test_create_agent_token_binds_family_id():
    """family_id 被加密绑定进 token, 不可篡改 (不同 fid 解出不同值)."""
    p1 = _decode(create_agent_token(family_id="family-A"))
    p2 = _decode(create_agent_token(family_id="family-B"))
    assert p1["fid"] == "family-A"
    assert p2["fid"] == "family-B"


def test_create_agent_token_expiry_matches_ttl():
    """exp - iat 应等于 _AGENT_TOKEN_TTL_SECONDS (300s)."""
    payload = _decode(create_agent_token(family_id="fam-ttl"))
    assert payload["exp"] - payload["iat"] == _AGENT_TOKEN_TTL_SECONDS


def test_create_agent_token_iat_is_recent():
    """iat 应接近当前时间 (容差 10s)."""
    before = datetime.now(UTC) - timedelta(seconds=10)
    payload = _decode(create_agent_token(family_id="fam-time"))
    after = datetime.now(UTC) + timedelta(seconds=10)
    iat = datetime.fromtimestamp(payload["iat"], tz=UTC)
    assert before <= iat <= after


def test_create_agent_token_algorithm_is_hs256():
    """token header 应声明 HS256."""
    token = create_agent_token(family_id="fam-alg")
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"


def test_create_agent_token_wrong_secret_rejected():
    """用错误密钥解码应抛 InvalidSignatureError (防篡改)."""
    token = create_agent_token(family_id="fam-tamper")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "wrong-secret-key", algorithms=[ALGORITHM])


def test_create_agent_token_tampered_payload_rejected():
    """篡改 payload 后签名失效, 解码应抛 InvalidSignatureError."""
    token = create_agent_token(family_id="fam-legit")
    header_b64, payload_b64, sig_b64 = token.split(".")
    # 伪造一个 fid 不同的 payload (不重新签名)
    forged_payload = (
        jwt.encode(
            {
                "sub": "agent",
                "fid": "fam-ATTACKER",
                "agt": "backend",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(seconds=300),
                "type": "agent",
            },
            "attacker-key",
            algorithm=ALGORITHM,
        ).split(".")[1]
    )
    forged_token = f"{header_b64}.{forged_payload}.{sig_b64}"
    with pytest.raises(jwt.InvalidSignatureError):
        _decode(forged_token)


def test_create_agent_token_expired_token_rejected():
    """过期 token 解码应抛 ExpiredSignatureError."""
    # 手动构造一个已过期的 token
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": "agent",
            "fid": "fam-old",
            "agt": "backend",
            "iat": now - timedelta(seconds=600),
            "exp": now - timedelta(seconds=300),  # 已过期
            "type": "agent",
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        _decode(expired)


def test_create_agent_token_distinct_tokens_for_distinct_calls():
    """连续两次调用 (不同 fid) 应产生不同 token 字符串."""
    t1 = create_agent_token(family_id="fam-1")
    t2 = create_agent_token(family_id="fam-2")
    assert t1 != t2
