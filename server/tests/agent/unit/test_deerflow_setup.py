"""Unit tests for Unit 4: DeerFlow harness import and config structure.

Note: DeerFlow is installed via git dependency (see pyproject.toml [tool.uv.sources]),
not vendored locally. Vendor manifest tests are skipped.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


class TestDeerFlowImport:
    def test_deerflow_client_importable(self):
        """DeerFlow harness must be importable via git dependency."""
        try:
            from deerflow.client import DeerFlowClient  # noqa: F401
            assert True
        except ImportError as e:
            raise AssertionError(
                f"deerflow.client not importable — check uv.lock for git dependency\n{e}"
            ) from e

    def test_deerflow_agents_importable(self):
        try:
            from deerflow.agents import make_lead_agent  # noqa: F401
            assert True
        except ImportError as e:
            raise AssertionError(f"deerflow.agents not importable: {e}") from e


# TestVendorManifest tests removed — DeerFlow installed via git, not vendor
# See pyproject.toml [tool.uv.sources] for git dependency config


class TestDeerFlowConfigFiles:
    def _config_dir(self):
        return os.path.join(os.path.dirname(__file__), "../../../apps/agent/deerflow_config")

    def test_base_config_exists(self):
        path = os.path.join(self._config_dir(), "base/config.yaml")
        assert os.path.exists(path), f"Missing: {path}"

    def test_dev_config_exists(self):
        path = os.path.join(self._config_dir(), "dev/config.yaml")
        assert os.path.exists(path), f"Missing: {path}"

    def test_prod_config_exists(self):
        path = os.path.join(self._config_dir(), "prod/config.yaml")
        assert os.path.exists(path), f"Missing: {path}"

    def test_agent_profile_exists(self):
        path = os.path.join(self._config_dir(), "agents/family-finance-agent/profile.yaml")
        assert os.path.exists(path), f"Missing: {path}"

    def test_base_config_valid_yaml(self):
        import yaml
        path = os.path.join(self._config_dir(), "base/config.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "sandbox" in data
        assert data["sandbox"]["allow_host_bash"] is False

    def test_prod_config_has_allowlist(self):
        import yaml
        path = os.path.join(self._config_dir(), "prod/config.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "memory" in data
        assert "allowed_fact_categories" in data["memory"]
        assert len(data["memory"]["allowed_fact_categories"]) > 0

    def test_prod_config_sandbox_bash_disabled(self):
        import yaml
        path = os.path.join(self._config_dir(), "prod/config.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["sandbox"]["allow_host_bash"] is False
