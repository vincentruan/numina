"""Tests for DATA_ROOT derived path defaults in apps/agent/app/config.py."""

import os
from pathlib import Path
from unittest.mock import patch


def _make_agent_settings(**overrides):
    """Create a fresh AgentSettings instance with env overrides."""
    env = {
        **overrides,
    }
    with patch.dict(os.environ, env, clear=False):
        from apps.agent.app.config import AgentSettings

        return AgentSettings()


def _resolve(p: str) -> str:
    """Resolve a path the same way the validator does."""
    return str(Path(p).resolve())


class TestDataRootExpansion:
    def test_default_data_root_expands_tilde(self):
        s = _make_agent_settings()
        assert "~" not in s.DATA_ROOT
        assert Path(s.DATA_ROOT).is_absolute()

    def test_custom_data_root_is_resolved(self):
        s = _make_agent_settings(DATA_ROOT="/tmp/test-agent")
        assert _resolve("/tmp/test-agent") == s.DATA_ROOT


class TestDerivedPaths:
    def test_sessions_data_dir_derived_from_data_root(self):
        s = _make_agent_settings(DATA_ROOT="/tmp/test-agent")
        assert _resolve("/tmp/test-agent") + "/workspaces" == s.SESSIONS_DATA_DIR

    def test_agent_data_dir_derived_from_data_root(self):
        s = _make_agent_settings(DATA_ROOT="/tmp/test-agent")
        assert _resolve("/tmp/test-agent") + "/workspaces" == s.AGENT_DATA_DIR

    def test_log_dir_derived_from_data_root(self):
        s = _make_agent_settings(DATA_ROOT="/tmp/test-agent")
        assert _resolve("/tmp/test-agent") + "/logs" == s.LOG_DIR

    def test_deerflow_db_path_derived_from_data_root(self):
        s = _make_agent_settings(DATA_ROOT="/tmp/test-agent")
        assert _resolve("/tmp/test-agent") + "/db/deerflow-checkpoints.db" == s.DEERFLOW_DB_PATH


class TestExplicitOverrides:
    def test_explicit_sessions_data_dir_overrides_derived(self):
        s = _make_agent_settings(
            DATA_ROOT="/tmp/test-agent",
            SESSIONS_DATA_DIR="/custom/sessions",
        )
        assert s.SESSIONS_DATA_DIR == "/custom/sessions"

    def test_explicit_log_dir_overrides_derived(self):
        s = _make_agent_settings(
            DATA_ROOT="/tmp/test-agent",
            LOG_DIR="/var/log/agent",
        )
        assert s.LOG_DIR == "/var/log/agent"

    def test_explicit_deerflow_db_path_overrides_derived(self):
        s = _make_agent_settings(
            DATA_ROOT="/tmp/test-agent",
            DEERFLOW_DB_PATH="/custom/deerflow.db",
        )
        assert s.DEERFLOW_DB_PATH == "/custom/deerflow.db"
