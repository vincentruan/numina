"""学习相关工厂 — 进度、练习、统计、路径、任务。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from models import (
    ChildLearningStats,
    LearningAssignment,
    LearningPath,
    LearningPathItem,
    LearningProgress,
    LearningTopic,
    PracticeAttempt,
    PracticeSession,
    Question,
)
from factories.users import next_id


class LearningFactory:
    @staticmethod
    def get_or_create_progress(
        db: Session,
        *,
        child_id: int,
        topic_id: int,
        mastery_level: str = "unseen",
        mastery_score: float | None = None,
        attempts: int = 0,
        xp_earned: int = 0,
    ) -> tuple[LearningProgress, bool]:
        existing = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .first()
        )
        if existing:
            return existing, False

        progress = LearningProgress(
            id=next_id(),
            child_id=child_id,
            topic_id=topic_id,
            mastery_level=mastery_level,
            mastery_score=mastery_score,
            attempts=attempts,
            xp_earned=xp_earned,
        )
        db.add(progress)
        db.flush()
        return progress, True

    @staticmethod
    def get_or_create_stats(
        db: Session,
        *,
        child_id: int,
        family_id: int,
        cumulative_xp: int = 0,
        level: int = 1,
        streak: int = 0,
        zone: str | None = None,
    ) -> tuple[ChildLearningStats, bool]:
        existing = (
            db.query(ChildLearningStats)
            .filter_by(child_id=child_id)
            .first()
        )
        if existing:
            return existing, False

        stats = ChildLearningStats(
            id=next_id(),
            child_id=child_id,
            family_id=family_id,
            cumulative_xp=cumulative_xp,
            level=level,
            learning_streak_days=streak,
            current_zone=zone or "growth",
            onboarding_completed=True,
        )
        db.add(stats)
        db.flush()
        return stats, True

    @staticmethod
    def create_practice_session(
        db: Session,
        *,
        child_id: int,
        topic_id: int,
        question_ids: list[int] | None = None,
        total_score: float | None = None,
        completed_count: int = 0,
        session_mode: str = "free",
        started_at: datetime | None = None,
    ) -> PracticeSession:
        ps = PracticeSession(
            id=next_id(),
            child_id=child_id,
            topic_id=topic_id,
            session_mode=session_mode,
            question_ids_json=json.dumps([str(qid) for qid in (question_ids or [])]),
            total_score=total_score,
            completed_count=completed_count,
            source="adaptive",
        )
        db.add(ps)
        db.flush()
        return ps

    @staticmethod
    def create_question(
        db: Session,
        *,
        topic_id: int,
        stem: str = "测试题目",
        answer_json: str = '{"correct": "A"}',
        difficulty: int = 3,
    ) -> Question:
        q = Question(
            id=next_id(),
            topic_id=topic_id,
            question_type="multiple_choice",
            stem=stem,
            answer_json=answer_json,
            difficulty=difficulty,
            bloom_level="apply",
            source="seed",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()
        return q

    @staticmethod
    def create_attempt(
        db: Session,
        *,
        session_id: int,
        question_id: int,
        child_id: int,
        topic_id: int,
        is_correct: bool = True,
        time_spent: int = 30,
    ) -> PracticeAttempt:
        attempt = PracticeAttempt(
            id=next_id(),
            session_id=session_id,
            question_id=question_id,
            child_id=child_id,
            topic_id=topic_id,
            user_answer_json="A",
            is_correct=is_correct,
            time_spent_seconds=time_spent,
        )
        db.add(attempt)
        db.flush()
        return attempt

    @staticmethod
    def create_path(
        db: Session,
        *,
        family_id: int,
        child_id: int,
        name: str = "学习路径",
        topic_ids: list[int] | None = None,
        created_by: int = 0,
    ) -> LearningPath:
        path = LearningPath(
            id=next_id(),
            family_id=family_id,
            child_id=child_id,
            created_by=created_by,
            name=name,
            status="active",
        )
        db.add(path)
        db.flush()

        if topic_ids:
            for i, tid in enumerate(topic_ids):
                item = LearningPathItem(
                    id=next_id(),
                    path_id=path.id,
                    topic_id=tid,
                    sort_order=i,
                    status="pending",
                )
                db.add(item)
            db.flush()

        return path

    @staticmethod
    def create_assignment(
        db: Session,
        *,
        family_id: int,
        child_id: int,
        topic_id: int,
        assignment_type: str = "parent_assigned",
        status: str = "pending",
        created_by: int = 0,
    ) -> LearningAssignment:
        assignment = LearningAssignment(
            id=next_id(),
            family_id=family_id,
            child_id=child_id,
            topic_id=topic_id,
            created_by=created_by,
            assignment_type=assignment_type,
            status=status,
        )
        db.add(assignment)
        db.flush()
        return assignment

    @staticmethod
    def find_topic_ids_by_keys(
        db: Session, topic_keys: list[str]
    ) -> dict[str, int]:
        """Look up topic IDs by topic_key. Returns {key: id} for found topics."""
        topics = (
            db.query(LearningTopic)
            .filter(LearningTopic.topic_key.in_(topic_keys))
            .all()
        )
        return {t.topic_key: t.id for t in topics}
