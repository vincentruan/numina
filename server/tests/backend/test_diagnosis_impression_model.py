"""DiagnosisImpression model round-trip tests."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.db.models.family import Family
from packages.db.models.learning.diagnosis_impression import DiagnosisImpression
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


class TestDiagnosisImpressionModel:
    def test_create_and_query_round_trip(self, db: Session) -> None:
        family = Family(name="T Family", invite_code="T001", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child", password_hash="x", role="child", family_id=family.id
        )
        db.add(child)
        db.flush()

        target = LearningTopic(
            id=1000000000001,
            topic_key="target_topic",
            name="Target",
            name_zh="目标",
            topic_type="knowledge_point", subject="math",
        )
        rec = LearningTopic(
            id=1000000000002,
            topic_key="rec_topic",
            name="Recommendation",
            name_zh="推荐",
            topic_type="knowledge_point", subject="math",
        )
        db.add_all([target, rec])
        db.flush()

        impression = DiagnosisImpression(
            child_id=child.id,
            target_topic_id=target.id,
            recommended_topic_id=rec.id,
            bkt_mastery=0.42,
            sample_size=6,
            config_version="v1",
        )
        db.add(impression)
        db.commit()
        db.refresh(impression)

        rows = db.query(DiagnosisImpression).filter_by(child_id=child.id).all()
        assert len(rows) == 1
        assert rows[0].bkt_mastery == 0.42
        assert rows[0].sample_size == 6
        assert rows[0].config_version == "v1"
        assert rows[0].target_topic_id == target.id
        assert rows[0].recommended_topic_id == rec.id

    def test_no_unique_constraint_allows_refresh_multiplicity(
        self, db: Session
    ) -> None:
        """Two records for the same (child, target, recommended) tuple both persist.

        SC measurement may over-count on refreshes (accepted limitation per AS1);
        the schema does not dedupe by key.
        """
        family = Family(name="T Family", invite_code="T002", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child", password_hash="x", role="child", family_id=family.id
        )
        db.add(child)
        db.flush()

        t = LearningTopic(
            id=1000000000011,
            topic_key="t",
            name="t",
            name_zh="t",
            topic_type="kp", subject="m",
        )
        r = LearningTopic(
            id=1000000000012,
            topic_key="r",
            name="r",
            name_zh="r",
            topic_type="kp", subject="m",
        )
        db.add_all([t, r])
        db.flush()

        for _ in range(2):
            db.add(
                DiagnosisImpression(
                    child_id=child.id,
                    target_topic_id=t.id,
                    recommended_topic_id=r.id,
                    bkt_mastery=0.3,
                    sample_size=3,
                    config_version="v1",
                )
            )
        db.commit()

        count = db.execute(
            text(
                "SELECT COUNT(*) FROM diagnosis_impressions "
                "WHERE child_id = :cid AND target_topic_id = :tid "
                "AND recommended_topic_id = :rid"
            ),
            {"cid": child.id, "tid": t.id, "rid": r.id},
        ).scalar_one()
        assert count == 2
