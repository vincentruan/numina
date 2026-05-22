"""Unit tests for packages/core/path_manager.py."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


@pytest.fixture
def tmp_data_root(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    from packages.core.path_manager import PathManager
    return PathManager(data_root=tmp_data_root)


class TestPathManagerInit:
    def test_creates_base_dirs(self, tmp_data_root):
        from packages.core.path_manager import PathManager
        PathManager(data_root=tmp_data_root)
        assert (tmp_data_root / "db").is_dir()
        assert (tmp_data_root / "logs").is_dir()
        assert (tmp_data_root / "backups").is_dir()
        assert (tmp_data_root / "workspaces" / "builtin").is_dir()
        assert (tmp_data_root / "workspaces" / "tenants").is_dir()
        assert (tmp_data_root / "runtime" / "effective").is_dir()

    def test_expands_tilde(self, monkeypatch, tmp_path):
        from packages.core.path_manager import PathManager
        monkeypatch.setenv("HOME", str(tmp_path))
        pm = PathManager(data_root="~/mydata")
        assert str(pm.data_root).startswith(str(tmp_path))

    def test_resolves_path(self, tmp_data_root):
        from packages.core.path_manager import PathManager
        pm = PathManager(data_root=tmp_data_root)
        assert pm.data_root.is_absolute()

    def test_reads_data_root_env(self, monkeypatch, tmp_path):
        from packages.core.path_manager import PathManager
        env_root = tmp_path / "env_data"
        monkeypatch.setenv("DATA_ROOT", str(env_root))
        pm = PathManager()
        assert pm.data_root == env_root.resolve()

    def test_explicit_arg_overrides_env(self, monkeypatch, tmp_path):
        from packages.core.path_manager import PathManager
        monkeypatch.setenv("DATA_ROOT", str(tmp_path / "env_data"))
        explicit = tmp_path / "explicit_data"
        pm = PathManager(data_root=explicit)
        assert pm.data_root == explicit.resolve()


class TestCorePathProperties:
    def test_db_dir(self, pm, tmp_data_root):
        assert pm.db_dir == tmp_data_root.resolve() / "db"

    def test_logs_dir(self, pm, tmp_data_root):
        assert pm.logs_dir == tmp_data_root.resolve() / "logs"

    def test_backups_dir(self, pm, tmp_data_root):
        assert pm.backups_dir == tmp_data_root.resolve() / "backups"


class TestBuiltinPaths:
    def test_builtin_root(self, pm, tmp_data_root):
        assert pm.builtin_root == tmp_data_root.resolve() / "workspaces" / "builtin"

    def test_builtin_agents_dir(self, pm, tmp_data_root):
        assert pm.builtin_agents_dir == tmp_data_root.resolve() / "workspaces" / "builtin" / "agents"

    def test_builtin_skills_dir(self, pm, tmp_data_root):
        assert pm.builtin_skills_dir == tmp_data_root.resolve() / "workspaces" / "builtin" / "skills"

    def test_builtin_mcp_dir(self, pm, tmp_data_root):
        assert pm.builtin_mcp_dir == tmp_data_root.resolve() / "workspaces" / "builtin" / "mcp"

    def test_builtin_agent_dir(self, pm, tmp_data_root):
        result = pm.builtin_agent_dir("my-agent")
        assert result == tmp_data_root.resolve() / "workspaces" / "builtin" / "agents" / "my-agent"

    def test_builtin_skill_dir(self, pm, tmp_data_root):
        result = pm.builtin_skill_dir("my-skill")
        assert result == tmp_data_root.resolve() / "workspaces" / "builtin" / "skills" / "my-skill"


class TestSlugValidation:
    @pytest.mark.parametrize("slug", [
        "asset-health",
        "a",
        "abc123",
        "my-agent-v2",
        "a0",
    ])
    def test_valid_slugs_accepted(self, pm, slug):
        # Should not raise
        result = pm.builtin_agent_dir(slug)
        assert slug in str(result)

    @pytest.mark.parametrize("slug,reason", [
        ("", "empty"),
        ("../etc/passwd", "traversal"),
        ("Agent-Name", "uppercase"),
        ("123abc", "digit start"),
        ("-leading-dash", "dash start"),
        ("has_underscore", "underscore"),
        ("has space", "space"),
        ("a/b", "slash"),
        ("a" * 256, "too long"),
    ])
    def test_invalid_slugs_rejected(self, pm, slug, reason):
        from packages.core.path_manager import PathSecurityError
        with pytest.raises(PathSecurityError, match="无效的"):
            pm.builtin_agent_dir(slug)


class TestThreadIdValidation:
    def test_valid_uuid_accepted(self, pm):
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = pm.tenant_session_dir(1, "my-agent", valid_uuid)
        assert valid_uuid in str(result)

    @pytest.mark.parametrize("bad_id", [
        "",
        "not-a-uuid",
        "550e8400-e29b-41d4-a716",
        "550e8400e29b41d4a716446655440000",
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
    ])
    def test_invalid_thread_id_rejected(self, pm, bad_id):
        from packages.core.path_manager import PathSecurityError
        with pytest.raises(PathSecurityError, match="无效的.*thread_id"):
            pm.tenant_session_dir(1, "my-agent", bad_id)


class TestAssertUnderRoot:
    def test_accepts_path_under_root(self, pm, tmp_data_root):
        path = tmp_data_root / "db" / "some.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        result = pm.assert_under_root(path)
        assert result.is_absolute()

    def test_rejects_path_outside_root(self, pm, tmp_path):
        outside = tmp_path / "outside" / "file.txt"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.touch()
        from packages.core.path_manager import PathSecurityError
        with pytest.raises(PathSecurityError):
            pm.assert_under_root(outside)

    def test_rejects_traversal_path(self, pm, tmp_data_root):
        traversal = tmp_data_root / "db" / ".." / ".." / "etc" / "passwd"
        from packages.core.path_manager import PathSecurityError
        with pytest.raises(PathSecurityError):
            pm.assert_under_root(traversal)

    def test_rejects_symlink_escape(self, pm, tmp_data_root, tmp_path):
        # Create a symlink inside data_root that points outside
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        link = tmp_data_root / "db" / "escape_link"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside_dir)
        from packages.core.path_manager import PathSecurityError
        with pytest.raises(PathSecurityError):
            pm.assert_under_root(link)


class TestAssertTenantAccess:
    def test_accepts_own_tenant_path(self, pm, tmp_data_root):
        family_id = 42
        tenant_path = pm.tenant_root(family_id) / "agents" / "my-agent"
        tenant_path.mkdir(parents=True, exist_ok=True)
        result = pm.assert_tenant_access(tenant_path, family_id)
        assert result.is_absolute()

    def test_rejects_other_tenant_path(self, pm):
        from packages.core.path_manager import PathSecurityError
        other_tenant_path = pm.tenant_root(99) / "agents" / "my-agent"
        other_tenant_path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(PathSecurityError):
            pm.assert_tenant_access(other_tenant_path, family_id=1)

    def test_rejects_builtin_as_tenant(self, pm):
        from packages.core.path_manager import PathSecurityError
        builtin_path = pm.builtin_agents_dir / "some-agent"
        builtin_path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(PathSecurityError):
            pm.assert_tenant_access(builtin_path, family_id=1)
