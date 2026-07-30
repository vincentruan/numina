"""Unit tests for packages/core/path_manager.py."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from packages.core.path_manager import PathSecurityError


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


class TestGetPathManager:
    def test_singleton_returns_same_instance(self):
        """get_path_manager() must return the same PathManager on repeated calls."""
        import packages.core as core_mod
        original = getattr(core_mod, "_path_manager", None)
        core_mod._path_manager = None
        try:
            from packages.core import get_path_manager
            pm1 = get_path_manager()
            pm2 = get_path_manager()
            assert pm1 is pm2
        finally:
            core_mod._path_manager = original

    def test_singleton_creates_path_manager_instance(self):
        """get_path_manager() must return a PathManager instance."""
        import packages.core as core_mod
        original = getattr(core_mod, "_path_manager", None)
        core_mod._path_manager = None
        try:
            from packages.core import get_path_manager
            from packages.core.path_manager import PathManager
            pm = get_path_manager()
            assert isinstance(pm, PathManager)
        finally:
            core_mod._path_manager = original


class TestTenantPaths:
    def test_tenant_root(self, pm, tmp_data_root):
        result = pm.tenant_root(12345)
        assert result == tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"

    def test_tenant_uploads_dir(self, pm, tmp_data_root):
        result = pm.tenant_uploads_dir(12345, 67890)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "uploads" / "67890"
        )

    def test_tenant_agent_dir(self, pm, tmp_data_root):
        result = pm.tenant_agent_dir(12345, "my-agent")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent"
        )

    def test_tenant_session_dir(self, pm, tmp_data_root):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_dir(12345, "my-agent", tid)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent" / "sessions" / tid
        )

    def test_tenant_session_events_file(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_events_file(12345, "my-agent", tid)
        assert result.name == "events.jsonl"
        assert result.parent == pm.tenant_session_dir(12345, "my-agent", tid)

    def test_tenant_session_artifacts_dir(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_artifacts_dir(12345, "my-agent", tid)
        assert result.name == "artifacts"
        assert result.parent == pm.tenant_session_dir(12345, "my-agent", tid)

    def test_tenant_memory_dir(self, pm, tmp_data_root):
        result = pm.tenant_memory_dir(12345, "my-agent")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent" / "memory"
        )

    def test_tenant_skills_dir(self, pm, tmp_data_root):
        result = pm.tenant_skills_dir(12345)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345" / "skills"
        )

    def test_tenant_skill_dir(self, pm, tmp_data_root):
        result = pm.tenant_skill_dir(12345, "my-skill")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "skills" / "my-skill"
        )

    def test_tenant_mcp_dir(self, pm, tmp_data_root):
        result = pm.tenant_mcp_dir(12345)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345" / "mcp"
        )

    def test_tenant_tmp_dir(self, pm, tmp_data_root):
        rid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_tmp_dir(12345, 67890, rid)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "tmp" / "67890" / rid
        )


class TestTenantIsolation:
    """Cross-tenant isolation: family A paths must not pass family B assertions."""

    def test_family_a_path_rejected_by_family_b_assert(self, pm):
        path_a = pm.tenant_root(11111) / "uploads" / "file.txt"
        path_a.parent.mkdir(parents=True, exist_ok=True)
        path_a.touch()
        with pytest.raises(PathSecurityError, match="租户越界"):
            pm.assert_tenant_access(path_a, 22222)

    def test_different_families_get_different_roots(self, pm):
        root_a = pm.tenant_root(11111)
        root_b = pm.tenant_root(22222)
        assert root_a != root_b
        assert "11111" in str(root_a)
        assert "22222" in str(root_b)

    def test_session_dirs_isolated_between_families(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        dir_a = pm.tenant_session_dir(11111, "my-agent", tid)
        dir_b = pm.tenant_session_dir(22222, "my-agent", tid)
        assert dir_a != dir_b
        assert "11111" in str(dir_a)
        assert "22222" in str(dir_b)


class TestEffectivePaths:
    def test_effective_dir(self, pm, tmp_data_root):
        result = pm.effective_dir(12345)
        assert result == tmp_data_root.resolve() / "runtime" / "effective" / "12345"

    def test_effective_agents_dir(self, pm):
        result = pm.effective_agents_dir(12345)
        assert result == pm.effective_dir(12345) / "agents"

    def test_effective_agent_dir(self, pm):
        result = pm.effective_agent_dir(12345, "my-agent")
        assert result == pm.effective_dir(12345) / "agents" / "my-agent"

    def test_effective_skills_dir(self, pm):
        result = pm.effective_skills_dir(12345)
        assert result == pm.effective_dir(12345) / "skills"

    def test_effective_extensions_file(self, pm):
        result = pm.effective_extensions_file(12345)
        assert result == pm.effective_dir(12345) / "extensions_config.json"

    def test_effective_agent_dir_validates_slug(self, pm):
        with pytest.raises(PathSecurityError, match="無效的|无效的"):
            pm.effective_agent_dir(12345, "../escape")
