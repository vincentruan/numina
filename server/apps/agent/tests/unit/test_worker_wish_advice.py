"""wish-advice worker dispatch branch unit tests (Plan B T7).

Verifies the dispatch branch is wired and the agent function exists with the
right signature + custom-event contract. Mirrors test_worker_finance_coach.py.
Full SSE integration is covered by the capability-cache integration path.
"""
import inspect

from apps.agent.services.runtime import worker


def test_wish_advice_dispatch_branch_exists():
    """The worker source has an `if app == "wish-advice":` branch."""
    src = inspect.getsource(worker)
    assert 'if app == "wish-advice":' in src


def test_run_wish_advice_agent_exists_with_expected_signature():
    """`_run_wish_advice_agent` mirrors `_run_finance_coach_agent` signature."""
    fn = getattr(worker, "_run_wish_advice_agent", None)
    assert fn is not None, "worker._run_wish_advice_agent must be defined"
    assert inspect.iscoroutinefunction(fn), "must be async"
    sig = inspect.signature(fn)
    expected = {
        "bridge", "run_manager", "record", "family_id", "user_id",
        "thread_id", "graph_input", "config",
    }
    assert expected.issubset(set(sig.parameters)), (
        f"missing params: {expected - set(sig.parameters)}"
    )


def test_synthetic_wish_advice_trigger_constant():
    """The skill-load fallback trigger message exists."""
    assert hasattr(worker, "_SYNTHETIC_WISH_ADVICE_TRIGGER")
    assert "/wish-advice" in worker._SYNTHETIC_WISH_ADVICE_TRIGGER


def test_wish_advice_result_event_emitted():
    """The worker emits a wish_advice.result custom event (schema-distinct from
    finance_coach.result, spec §7.1)."""
    src = inspect.getsource(worker._run_wish_advice_agent)
    assert '"type": "wish_advice.result"' in src
