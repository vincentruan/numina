"""finance-coach worker dispatch branch unit tests (Plan A T6).

Verifies the dispatch branch is wired and the agent function exists with the
right signature + custom-event contract. Full SSE integration is covered by
test_gateway_finance_coach.py (T5) + a later capability-cache integration test.
"""
import inspect

from apps.agent.services.runtime import worker


def test_finance_coach_dispatch_branch_exists():
    """The worker source has an `if app == "finance-coach":` branch."""
    src = inspect.getsource(worker)
    assert 'if app == "finance-coach":' in src


def test_run_finance_coach_agent_exists_with_expected_signature():
    """`_run_finance_coach_agent` mirrors `_run_import_parse_agent` signature."""
    fn = getattr(worker, "_run_finance_coach_agent", None)
    assert fn is not None, "worker._run_finance_coach_agent must be defined"
    assert inspect.iscoroutinefunction(fn), "must be async"
    sig = inspect.signature(fn)
    expected = {
        "bridge", "run_manager", "record", "family_id", "user_id",
        "thread_id", "graph_input", "config",
    }
    assert expected.issubset(set(sig.parameters)), (
        f"missing params: {expected - set(sig.parameters)}"
    )


def test_synthetic_finance_coach_trigger_constant():
    """The skill-load fallback trigger message exists."""
    assert hasattr(worker, "_SYNTHETIC_FINANCE_COACH_TRIGGER")
    assert "/finance-coach" in worker._SYNTHETIC_FINANCE_COACH_TRIGGER
