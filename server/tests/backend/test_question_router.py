"""Tests for question router and production pipeline."""
import pytest

from packages.db.models.learning.topic import LearningTopic
from apps.backend.app.services.learning.question_router import (
    route,
    generate_production_plan,
    RoutingResult,
)


@pytest.fixture
def topics(db_session):
    t1 = LearningTopic(topic_key="math.add", subject="mathematics", domain="number",
                       name="Addition", age_group="lower", deprecated=False,
                       topic_type="knowledge")
    t2 = LearningTopic(topic_key="math.pattern", subject="mathematics", domain="reasoning",
                       name="Pattern Finding", age_group="lower", deprecated=False,
                       topic_type="knowledge")
    db_session.add_all([t1, t2])
    db_session.flush()
    return [t1, t2]


class TestRouting:
    """Router selects generation method based on topic characteristics."""

    def test_calculation_topic_routes_to_template(self, db_session, topics):
        result = route(db_session, topics[0].id)
        assert result.method == "template"
        assert result.topic_id == topics[0].id

    def test_reasoning_topic_routes_to_llm(self, db_session, topics):
        result = route(db_session, topics[1].id)
        # Pattern finding → LLM generation (no parameterized template possible)
        assert result.method == "llm"

    def test_route_returns_recommended_count(self, db_session, topics):
        result = route(db_session, topics[0].id)
        assert result.recommended_count >= 1


class TestProductionPlan:
    """Production plan allocates capacity across gaps."""

    def test_plan_respects_capacity(self, db_session, topics):
        gaps = [
            {"topic_id": topics[0].id, "prerequisite_value": 0.8},
            {"topic_id": topics[1].id, "prerequisite_value": 0.5},
        ]
        plan = generate_production_plan(db_session, gaps, weekly_capacity=10)
        total = sum(t.count for t in plan)
        assert total <= 10

    def test_plan_prioritizes_high_prerequisite_value(self, db_session, topics):
        gaps = [
            {"topic_id": topics[1].id, "prerequisite_value": 0.3},
            {"topic_id": topics[0].id, "prerequisite_value": 0.9},
        ]
        plan = generate_production_plan(db_session, gaps, weekly_capacity=10)
        # Higher prereq value topic should be first
        assert plan[0].topic_id == topics[0].id or len(plan) == 1
