"""AI Extraction Circuit breaker adapter.

This adapter bridges the unified FSM with the AIExtractionCircuit entity
which uses a different vocabulary (ok/rate_limited/circuit_open) and
threshold-driven evaluation (audit table counting).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.services.circuit_breaker.adapters.base import (
    CircuitBreakerAdapter,
)
from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.utils.snowflake import next_id

# Thresholds from docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md
RATE_LIMIT_WINDOW_MINUTES = 60
RATE_LIMIT_THRESHOLD = 5
RATE_LIMIT_COOLDOWN_MINUTES = 30
CIRCUIT_OPEN_WINDOW_HOURS = 24
CIRCUIT_OPEN_THRESHOLD = 20

FALLBACK_METHOD = "llm_fallback_hit"


class ExtractionAdapter(CircuitBreakerAdapter):
    """Adapter for AIExtractionCircuit entity.

    Uses threshold-driven evaluation (audit table counting) rather than
    event-driven failure recording. Vocabulary mapping:
    - ok -> closed (healthy)
    - rate_limited -> open (temporary, 30min auto-expire)
    - circuit_open -> open (permanent, manual reset required)
    """

    def __init__(self, family_id: int, skill_id: str) -> None:
        self._family_id = int(family_id)
        self._skill_id = skill_id
        self._circuit: AIExtractionCircuit | None = None

    def bind(self, entity: object) -> None:
        """Bind a pre-loaded AIExtractionCircuit to skip the DB query."""
        self._circuit = entity  # type: ignore[assignment]

    def get_config(self) -> CircuitBreakerConfig:
        """Return config matching extraction behavior."""
        return CircuitBreakerConfig(
            transient_failure_threshold=CIRCUIT_OPEN_THRESHOLD,
            half_open_success_threshold=1,  # Not used
            recovery_cooldown_seconds=RATE_LIMIT_COOLDOWN_MINUTES * 60,
            auto_recovery_seconds=RATE_LIMIT_COOLDOWN_MINUTES * 60,
            requires_manual_reset=True,  # For circuit_open
        )

    def load_entity(self, db: Session) -> AIExtractionCircuit | None:
        """Load or create circuit entity with row locking.

        Uses with_for_update() to prevent concurrent create-on-miss races.
        Falls back to re-query on IntegrityError (unique constraint on
        family_id + skill_id) in case another request created the row first.
        """
        if self._circuit is not None:
            return self._circuit
        self._circuit = (
            db.query(AIExtractionCircuit)
            .filter_by(family_id=self._family_id, skill_id=self._skill_id)
            .with_for_update()
            .first()
        )
        if self._circuit is None:
            # Create new circuit
            self._circuit = AIExtractionCircuit(
                id=next_id(),
                family_id=self._family_id,
                skill_id=self._skill_id,
                state="ok",
                last_evaluated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            db.add(self._circuit)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # Another request created it first; re-query
                self._circuit = (
                    db.query(AIExtractionCircuit)
                    .filter_by(family_id=self._family_id, skill_id=self._skill_id)
                    .with_for_update()
                    .first()
                )
            else:
                db.refresh(self._circuit)
        return self._circuit

    def persist(self, db: Session) -> None:
        """Commit changes to DB."""
        try:
            db.commit()
        except Exception:
            db.rollback()

    def is_open(self, db: Session) -> tuple[bool, str | None]:
        """Check if circuit is open (blocking).

        Returns (is_blocked, reason) where reason is "rate_limited" or "circuit_open".
        Auto-recovers expired rate_limited to ok.
        """
        circuit = self.load_entity(db)
        if circuit is None or circuit.state == "ok":
            return False, None

        if circuit.state == "circuit_open":
            return True, "circuit_open"

        if circuit.state == "rate_limited":
            if circuit.opened_until is not None and circuit.opened_until > datetime.now(UTC).replace(tzinfo=None):
                return True, "rate_limited"
            # Rate limit window expired -> auto-recover to ok
            circuit.state = "ok"
            circuit.opened_at = None
            circuit.opened_until = None
            circuit.last_evaluated_at = datetime.now(UTC).replace(tzinfo=None)
            try:
                db.commit()
            except Exception:
                db.rollback()
            return False, None

        return False, None

    def evaluate(self, db: Session) -> str:
        """Evaluate circuit state based on audit table counts.

        Returns new state string. circuit_open takes priority over rate_limited.
        """
        now = datetime.now(UTC).replace(tzinfo=None)

        # 24h threshold (circuit_open has highest priority)
        circuit_window_start = now - timedelta(hours=CIRCUIT_OPEN_WINDOW_HOURS)
        circuit_count = (
            db.query(func.count(AIExtractionAudit.id))
            .filter(
                AIExtractionAudit.family_id == self._family_id,
                AIExtractionAudit.skill_id == self._skill_id,
                AIExtractionAudit.method == FALLBACK_METHOD,
                AIExtractionAudit.extracted_at >= circuit_window_start,
            )
            .scalar()
        ) or 0

        if circuit_count >= CIRCUIT_OPEN_THRESHOLD:
            return self._upsert_state(
                "circuit_open", opened_at=now, opened_until=None, db=db
            )

        # 1h threshold
        rate_window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        rate_count = (
            db.query(func.count(AIExtractionAudit.id))
            .filter(
                AIExtractionAudit.family_id == self._family_id,
                AIExtractionAudit.skill_id == self._skill_id,
                AIExtractionAudit.method == FALLBACK_METHOD,
                AIExtractionAudit.extracted_at >= rate_window_start,
            )
            .scalar()
        ) or 0

        if rate_count >= RATE_LIMIT_THRESHOLD:
            return self._upsert_state(
                "rate_limited",
                opened_at=now,
                opened_until=now + timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES),
                db=db,
            )

        # Below thresholds -> maintain/recover to ok
        return self._upsert_state("ok", opened_at=None, opened_until=None, db=db)

    def reset(self, user_id: int, db: Session) -> bool:
        """Manual admin reset to ok state.

        Records manually_reset_at and reset_by_user_id.
        """
        circuit = self.load_entity(db)
        if circuit is None:
            return False

        circuit.state = "ok"
        circuit.opened_at = None
        circuit.opened_until = None
        circuit.manually_reset_at = datetime.now(UTC).replace(tzinfo=None)
        circuit.reset_by_user_id = int(user_id)
        circuit.last_evaluated_at = datetime.now(UTC).replace(tzinfo=None)
        try:
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def _upsert_state(
        self,
        new_state: str,
        opened_at: datetime | None,
        opened_until: datetime | None,
        db: Session,
    ) -> str:
        """Update circuit state."""
        circuit = self.load_entity(db)
        if circuit is None:
            return new_state

        circuit.state = new_state
        circuit.opened_at = opened_at
        circuit.opened_until = opened_until
        circuit.last_evaluated_at = datetime.now(UTC).replace(tzinfo=None)
        try:
            db.commit()
        except Exception:
            db.rollback()
        return new_state
