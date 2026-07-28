"""AI 提取熔断服务 — 三段式状态机 + SQL 时间窗口计数。

阈值（来自 docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md D7）：
- 1h 内 fallback 触发 ≥ 5 次 → state=rate_limited，opened_until=now+30min
- 24h 内 fallback 触发 ≥ 20 次 → state=circuit_open，需手动重置
- circuit_open 优先级高于 rate_limited
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.utils.snowflake import next_id

RATE_LIMIT_WINDOW_MINUTES = 60
RATE_LIMIT_THRESHOLD = 5
RATE_LIMIT_COOLDOWN_MINUTES = 30
CIRCUIT_OPEN_WINDOW_HOURS = 24
CIRCUIT_OPEN_THRESHOLD = 20

FALLBACK_METHOD = "llm_fallback_hit"


class AIExtractionCircuitService:
    @staticmethod
    def _get_or_create(
        family_id: int, skill_id: str, db: Session
    ) -> AIExtractionCircuit:
        circuit = (
            db.query(AIExtractionCircuit)
            .filter_by(family_id=family_id, skill_id=skill_id)
            .first()
        )
        if circuit is None:
            circuit = AIExtractionCircuit(
                id=next_id(),
                family_id=family_id,
                skill_id=skill_id,
                state="ok",
                last_evaluated_at=datetime.utcnow(),
            )
            db.add(circuit)
            db.commit()
            db.refresh(circuit)
        return circuit

    @staticmethod
    def is_open(
        family_id: int | str, skill_id: str, db: Session
    ) -> tuple[bool, str | None]:
        """扫描请求发起前调用。返回 (是否阻塞, 阻塞原因)。

        过期的 rate_limited 自动转回 ok 并返回 (False, None)。
        """
        fid = int(family_id)
        circuit = (
            db.query(AIExtractionCircuit)
            .filter_by(family_id=fid, skill_id=skill_id)
            .first()
        )
        if circuit is None or circuit.state == "ok":
            return False, None

        if circuit.state == "circuit_open":
            return True, "circuit_open"

        if circuit.state == "rate_limited":
            if circuit.opened_until is not None and circuit.opened_until > datetime.utcnow():
                return True, "rate_limited"
            # 限流窗口已过 → 自动恢复 ok
            circuit.state = "ok"
            circuit.opened_at = None
            circuit.opened_until = None
            circuit.last_evaluated_at = datetime.utcnow()
            try:
                db.commit()
            except Exception:
                db.rollback()
            return False, None

        return False, None

    @staticmethod
    def evaluate(family_id: int | str, skill_id: str, db: Session) -> str:
        """每次扫描结束（成功 or 失败）后调用。基于 audit 表时间窗口计数转移状态。

        返回新 state 字符串。circuit_open 优先级高于 rate_limited。
        """
        fid = int(family_id)
        now = datetime.utcnow()

        # 24h 阈值（circuit_open 优先级最高）
        circuit_window_start = now - timedelta(hours=CIRCUIT_OPEN_WINDOW_HOURS)
        circuit_count = (
            db.query(func.count(AIExtractionAudit.id))
            .filter(
                AIExtractionAudit.family_id == fid,
                AIExtractionAudit.skill_id == skill_id,
                AIExtractionAudit.method == FALLBACK_METHOD,
                AIExtractionAudit.extracted_at >= circuit_window_start,
            )
            .scalar()
        ) or 0

        if circuit_count >= CIRCUIT_OPEN_THRESHOLD:
            return AIExtractionCircuitService._upsert_state(
                fid, skill_id, "circuit_open", opened_at=now, opened_until=None, db=db
            )

        # 1h 阈值
        rate_window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        rate_count = (
            db.query(func.count(AIExtractionAudit.id))
            .filter(
                AIExtractionAudit.family_id == fid,
                AIExtractionAudit.skill_id == skill_id,
                AIExtractionAudit.method == FALLBACK_METHOD,
                AIExtractionAudit.extracted_at >= rate_window_start,
            )
            .scalar()
        ) or 0

        if rate_count >= RATE_LIMIT_THRESHOLD:
            return AIExtractionCircuitService._upsert_state(
                fid,
                skill_id,
                "rate_limited",
                opened_at=now,
                opened_until=now + timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES),
                db=db,
            )

        # 都未达阈值 → 维持/恢复 ok
        return AIExtractionCircuitService._upsert_state(
            fid, skill_id, "ok", opened_at=None, opened_until=None, db=db
        )

    @staticmethod
    def _upsert_state(
        family_id: int,
        skill_id: str,
        new_state: str,
        opened_at: datetime | None,
        opened_until: datetime | None,
        db: Session,
    ) -> str:
        circuit = AIExtractionCircuitService._get_or_create(family_id, skill_id, db)
        circuit.state = new_state
        circuit.opened_at = opened_at
        circuit.opened_until = opened_until
        circuit.last_evaluated_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
        return new_state

    @staticmethod
    def reset(
        family_id: int | str, skill_id: str, user_id: int | str, db: Session
    ) -> bool:
        """管理员手工重置。state=ok，写入 manually_reset_at + reset_by_user_id。"""
        fid = int(family_id)
        uid = int(user_id)
        circuit = AIExtractionCircuitService._get_or_create(fid, skill_id, db)
        circuit.state = "ok"
        circuit.opened_at = None
        circuit.opened_until = None
        circuit.manually_reset_at = datetime.utcnow()
        circuit.reset_by_user_id = uid
        circuit.last_evaluated_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
            return False
        return True
