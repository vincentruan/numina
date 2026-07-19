"""bootstrap_agents idempotently seeds all system agents including finance-coach."""
from apps.backend.app.bootstrap.agents import bootstrap_agents
from apps.backend.app.constants.system_ids import FINANCE_COACH_AGENT_ID


def test_bootstrap_seeds_finance_coach_agent(db_session):
    """bootstrap_agents upserts the finance-coach system agent row."""
    bootstrap_agents(db_session)
    from apps.backend.app.models.ai_agent import AIAgent
    agent = db_session.query(AIAgent).filter_by(id=FINANCE_COACH_AGENT_ID).first()
    assert agent is not None
    assert agent.agent_name == "finance-coach"
    assert agent.agent_type == "system"
    assert agent.memory_enabled is False  # stateless — mirrors asset-report/import-parse
    assert agent.skills == ["finance-coach"]


def test_bootstrap_finance_coach_is_idempotent(db_session):
    """Running bootstrap twice does not duplicate or error."""
    bootstrap_agents(db_session)
    bootstrap_agents(db_session)  # second call must not raise
    from apps.backend.app.models.ai_agent import AIAgent
    count = db_session.query(AIAgent).filter_by(agent_name="finance-coach").count()
    assert count == 1
