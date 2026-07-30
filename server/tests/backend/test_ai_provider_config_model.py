from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)
from apps.backend.app.utils.snowflake import next_id


def test_ai_provider_config_fields(db):
    config = AIProviderConfig(
        family_id=next_id(),
        name="Claude 主力",
        provider="anthropic",
        api_key_encrypted="enc_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    assert config.id is not None
    assert config.name == "Claude 主力"
    assert config.is_active is True
    assert config.vision_model_id is None


def test_ai_provider_test_result_fields(db):
    config_id = next_id()
    result = AIProviderTestResult(
        config_id=config_id,
        test_type="main",
        success=True,
        message="连接成功",
        latency_ms=120,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    assert result.id is not None
    assert result.test_type == "main"
    assert result.success is True
