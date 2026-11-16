"""Service functions for topic hook questions."""

from sqlalchemy.orm import Session

from packages.db.models.learning.hook import TopicHookQuestion

#: Only human-reviewed rows are served to children. LLM-generated rows land as
#: ``pending`` and stay invisible until someone approves them.
APPROVED = "approved"


def get_hook_question(
    db: Session,
    topic_id: int,
    age_group: str = "mid",
) -> TopicHookQuestion | None:
    """Get the approved hook question for a topic + age group.

    Falls back to ``age_group='mid'`` when the requested age group has no
    approved row, so a topic seeded only at mid level still shows something to
    younger / older children.
    """
    def _approved(band: str) -> TopicHookQuestion | None:
        return (
            db.query(TopicHookQuestion)
            .filter(
                TopicHookQuestion.topic_id == topic_id,
                TopicHookQuestion.age_group == band,
                TopicHookQuestion.review_status == APPROVED,
            )
            .first()
        )

    row = _approved(age_group)
    if row is not None or age_group == "mid":
        return row
    return _approved("mid")
