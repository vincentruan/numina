"""Integration tests for circuit breaker adapters with real DB."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.models.asr_provider_config import ASRProviderConfig
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.circuit_breaker.adapters.ai_provider import (
    AIProviderAdapter,
)
from apps.backend.app.services.circuit_breaker.adapters.asr import ASRAdapter
from apps.backend.app.services.circuit_breaker.adapters.extraction import (
    ExtractionAdapter,
)
from apps.backend.app.services.circuit_breaker.adapters.web_search import (
    WebSearchAdapter,
)
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def ai_provider(db: Session) -> AIProviderConfig:
    """Create an AI provider config for testing."""
    cfg = AIProviderConfig(
        id=next_id(),
        family_id=1001,
        name="Test Provider",
        provider="openai",
        circuit_state="closed",
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@pytest.fixture
def web_search_provider(db: Session) -> FamilyWebSearchProvider:
    """Create a web search provider for testing."""
    p = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="tavily",
        is_enabled=True,
        circuit_state="closed",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def asr_config(db: Session) -> ASRProviderConfig:
    """Create an ASR config for testing."""
    cfg = ASRProviderConfig(
        id=next_id(),
        family_id=1001,
        name="Test ASR",
        provider="openai",
        is_active=True,
        circuit_state="closed",
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


class TestWebSearchAdapter:
    """Tests for WebSearchAdapter with DB."""

    def test_record_failure_opens_at_threshold(
        self, db: Session, web_search_provider: FamilyWebSearchProvider
    ) -> None:
        """Transient failures should open circuit at threshold."""
        adapter = WebSearchAdapter(web_search_provider.id)

        for _ in range(5):
            adapter.record_failure("transient_rate_limit", db)
            db.refresh(web_search_provider)

        assert web_search_provider.circuit_state == "open"
        assert web_search_provider.circuit_reason == "transient_rate_limit"

    def test_record_success_in_half_open_closes(
        self, db: Session, web_search_provider: FamilyWebSearchProvider
    ) -> None:
        """Success threshold in half_open should close circuit."""
        web_search_provider.circuit_state = "half_open"
        web_search_provider.half_open_success_count = 2
        web_search_provider.half_open_window_start = datetime.now(UTC).replace(
            tzinfo=None
        )
        db.commit()

        adapter = WebSearchAdapter(web_search_provider.id)
        adapter.record_success(db)
        db.refresh(web_search_provider)

        assert web_search_provider.circuit_state == "closed"
        assert web_search_provider.failure_count == 0

    def test_check_recovery_after_cooldown(
        self, db: Session, web_search_provider: FamilyWebSearchProvider
    ) -> None:
        """Circuit should recover after cooldown."""
        web_search_provider.circuit_state = "open"
        web_search_provider.circuit_reason = "transient_rate_limit"
        web_search_provider.last_failure_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(seconds=120)
        db.commit()

        adapter = WebSearchAdapter(web_search_provider.id)
        result = adapter.check_recovery(db)
        db.refresh(web_search_provider)

        assert result is True
        assert web_search_provider.circuit_state == "half_open"


class TestASRAdapter:
    """Tests for ASRAdapter with DB."""

    def test_record_failure_opens_and_disables(
        self, db: Session, asr_config: ASRProviderConfig
    ) -> None:
        """3 failures should open circuit and disable config."""
        adapter = ASRAdapter(asr_config.id)

        for _ in range(3):
            adapter.record_failure(db)
            db.refresh(asr_config)

        assert asr_config.circuit_state == "open"
        assert asr_config.is_active is False

    def test_record_success_closes_and_enables(
        self, db: Session, asr_config: ASRProviderConfig
    ) -> None:
        """Success should close circuit and reset failure count."""
        asr_config.circuit_state = "open"
        asr_config.failure_count = 3
        asr_config.is_active = False
        db.commit()

        adapter = ASRAdapter(asr_config.id)
        adapter.record_success(db)
        db.refresh(asr_config)

        assert asr_config.circuit_state == "closed"
        assert asr_config.failure_count == 0


class TestAIProviderAdapter:
    """Tests for AIProviderAdapter with DB."""

    def test_record_failure_opens_with_legacy_sync(
        self, db: Session, ai_provider: AIProviderConfig
    ) -> None:
        """Failure should open circuit and sync legacy fields."""
        adapter = AIProviderAdapter(ai_provider.id, ai_provider.family_id)

        for _ in range(5):
            adapter.record_failure("transient_rate_limit", db)
            db.refresh(ai_provider)

        assert ai_provider.circuit_state == "open"
        assert ai_provider.circuit_open is True
        assert ai_provider.circuit_open_until is not None

    def test_evaluate_half_open_window_high_success_rate_closes(
        self, db: Session, ai_provider: AIProviderConfig
    ) -> None:
        """Window expiry with high success rate closes circuit."""
        ai_provider.circuit_state = "half_open"
        ai_provider.half_open_success_count = 8
        ai_provider.half_open_failure_count = 2
        ai_provider.half_open_window_start = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(seconds=360)
        db.commit()

        adapter = AIProviderAdapter(ai_provider.id, ai_provider.family_id)
        transition = adapter.evaluate_half_open_window(db)
        db.refresh(ai_provider)

        assert transition is not None
        assert transition.changed is True
        assert ai_provider.circuit_state == "closed"
        assert ai_provider.circuit_open is False
        assert ai_provider.circuit_open_until is None

    def test_recovery_schedule_transitions_to_half_open(
        self, db: Session, ai_provider: AIProviderConfig
    ) -> None:
        """Schedule-based recovery should transition open -> half_open."""
        # Set minute to match pattern
        scheduled_minute = datetime.now(UTC).replace(tzinfo=None).minute
        schedule_suffix = f":{scheduled_minute:02d}"

        ai_provider.circuit_state = "open"
        ai_provider.circuit_reason = "transient_rate_limit"
        ai_provider.recovery_schedule = schedule_suffix
        ai_provider.last_failure_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(minutes=35)
        db.commit()

        adapter = AIProviderAdapter(ai_provider.id, ai_provider.family_id)
        result = adapter.attempt_recovery(db)

        db.refresh(ai_provider)
        assert result is True
        assert ai_provider.circuit_state == "half_open"

    def test_fallback_recovery_when_both_triggers_null(
        self, db: Session, ai_provider: AIProviderConfig
    ) -> None:
        """Fallback recovery should trigger after DEFAULT_RECOVERY_COOLDOWN when
        recovery_schedule and circuit_open_until are both NULL."""
        ai_provider.circuit_state = "open"
        ai_provider.circuit_reason = "permanent_account"
        ai_provider.circuit_open_until = None  # Manual recovery (from on_transition)
        ai_provider.recovery_schedule = None  # Never configured
        ai_provider.last_failure_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(hours=25)  # Past the 24h fallback cooldown
        db.commit()

        adapter = AIProviderAdapter(ai_provider.id, ai_provider.family_id)
        result = adapter.attempt_recovery(db)

        db.refresh(ai_provider)
        assert result is True
        assert ai_provider.circuit_state == "half_open"

    def test_fallback_recovery_not_triggered_before_cooldown(
        self, db: Session, ai_provider: AIProviderConfig
    ) -> None:
        """Fallback recovery should NOT trigger before cooldown elapses."""
        ai_provider.circuit_state = "open"
        ai_provider.circuit_reason = "permanent_account"
        ai_provider.circuit_open_until = None
        ai_provider.recovery_schedule = None
        ai_provider.last_failure_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(hours=1)  # Only 1h, well under 24h cooldown
        db.commit()

        adapter = AIProviderAdapter(ai_provider.id, ai_provider.family_id)
        result = adapter.attempt_recovery(db)

        db.refresh(ai_provider)
        assert result is False
        assert ai_provider.circuit_state == "open"


class TestExtractionAdapter:
    """Tests for ExtractionAdapter with DB."""

    def test_is_open_rate_limited_not_expired(self, db: Session) -> None:
        """Rate-limited circuit should block until expired."""
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=1,
            skill_id="test-skill",
            state="rate_limited",
            opened_at=datetime.now(UTC).replace(tzinfo=None),
            opened_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=20),
        )
        db.add(circuit)
        db.commit()

        adapter = ExtractionAdapter(1, "test-skill")
        blocked, reason = adapter.is_open(db)

        assert blocked is True
        assert reason == "rate_limited"

    def test_is_open_rate_limited_expired_auto_recovers(self, db: Session) -> None:
        """Expired rate-limited circuit should auto-recover."""
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=1,
            skill_id="test-skill",
            state="rate_limited",
            opened_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=40),
            opened_until=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10),
        )
        db.add(circuit)
        db.commit()

        adapter = ExtractionAdapter(1, "test-skill")
        blocked, reason = adapter.is_open(db)
        db.refresh(circuit)

        assert blocked is False
        assert reason is None
        assert circuit.state == "ok"

    def test_reset_records_admin_metadata(self, db: Session) -> None:
        """Reset should record manually_reset_at and reset_by_user_id."""
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=1,
            skill_id="test-skill",
            state="circuit_open",
            opened_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(circuit)
        db.commit()

        adapter = ExtractionAdapter(1, "test-skill")
        result = adapter.reset(42, db)
        db.refresh(circuit)

        assert result is True
        assert circuit.state == "ok"
        assert circuit.manually_reset_at is not None
        assert circuit.reset_by_user_id == 42
