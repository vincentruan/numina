"""Tests for packages.core.system_config loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from packages.core import system_config


@pytest.fixture(autouse=True)
def _clear_lru_cache():
    """Reset the lru_cache between tests so each gets a fresh load."""
    system_config.get_system_config.cache_clear()
    yield
    system_config.get_system_config.cache_clear()


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_get_max_tokens_default_real_file_gpt5():
    """Smoke: real system-config.yaml resolves gpt-5 to 128000."""
    assert system_config.get_max_tokens_default("gpt-5") == 128000
    assert system_config.get_max_tokens_default("gpt-5-mini") == 128000
    assert system_config.get_max_tokens_default("gpt-5.2-pro") == 128000


def test_get_max_tokens_default_real_file_claude():
    """Smoke: claude-sonnet-4-5 matches claude-sonnet-4 (longest-first ordering)."""
    assert system_config.get_max_tokens_default("claude-sonnet-4-5-20250929") == 64000
    assert system_config.get_max_tokens_default("claude-opus-4-5") == 64000
    assert system_config.get_max_tokens_default("claude-haiku-4") == 8192


def test_get_max_tokens_default_real_file_qwen3_max():
    assert system_config.get_max_tokens_default("qwen3-max") == 66000
    assert system_config.get_max_tokens_default("qwen3-32b") == 8192


def test_get_max_tokens_default_real_file_glm46():
    assert system_config.get_max_tokens_default("glm-4-6") == 128000
    assert system_config.get_max_tokens_default("glm-4.6") == 128000


def test_get_max_tokens_default_real_file_kimi():
    assert system_config.get_max_tokens_default("kimi-k2-0905") == 16384
    assert system_config.get_max_tokens_default("kimi-k2-thinking") == 16384


def test_get_max_tokens_default_unknown_model_returns_none():
    assert system_config.get_max_tokens_default("some-custom-fine-tune-v1") is None


def test_get_max_tokens_default_empty_or_none_returns_none():
    assert system_config.get_max_tokens_default("") is None
    assert system_config.get_max_tokens_default(None) is None


def test_get_max_tokens_default_case_insensitive():
    assert system_config.get_max_tokens_default("GPT-5") == 128000
    assert system_config.get_max_tokens_default("Claude-Sonnet-4-5") == 64000


def test_loader_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    cfg = system_config.get_system_config()
    assert cfg == {}


def test_loader_invalid_yaml_raises(tmp_path, monkeypatch):
    _write_yaml(tmp_path / "docker-compose.yml", "")  # marker
    _write_yaml(tmp_path / "system-config.yaml", "{ this is: not valid: yaml }: x:")
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    with pytest.raises(Exception):
        system_config.get_system_config()


def test_loader_local_override_deep_merges(tmp_path, monkeypatch):
    _write_yaml(tmp_path / "docker-compose.yml", "")
    _write_yaml(
        tmp_path / "system-config.yaml",
        """
        ai_models:
          max_tokens_defaults_by_prefix:
            - prefix: gpt-5
              max_tokens: 128000
        other:
          unrelated: keep_me
        """,
    )
    _write_yaml(
        tmp_path / "system-config.local.yaml",
        """
        ai_models:
          max_tokens_defaults_by_prefix:
            - prefix: my-private-model
              max_tokens: 4096
        """,
    )
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    cfg = system_config.get_system_config()
    # Local wins for ai_models.max_tokens_defaults_by_prefix (list replace, not merge)
    prefixes = [e["prefix"] for e in cfg["ai_models"]["max_tokens_defaults_by_prefix"]]
    assert prefixes == ["my-private-model"]
    # Untouched key retained
    assert cfg["other"]["unrelated"] == "keep_me"


def test_loader_negative_max_tokens_ignored(tmp_path, monkeypatch):
    _write_yaml(tmp_path / "docker-compose.yml", "")
    _write_yaml(
        tmp_path / "system-config.yaml",
        """
        ai_models:
          max_tokens_defaults_by_prefix:
            - prefix: bad-model
              max_tokens: -1
            - prefix: zero-model
              max_tokens: 0
            - prefix: ok-model
              max_tokens: 4096
        """,
    )
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    assert system_config.get_max_tokens_default("bad-model-v1") is None
    assert system_config.get_max_tokens_default("zero-model-v1") is None
    assert system_config.get_max_tokens_default("ok-model-v1") == 4096


def test_loader_malformed_entry_skipped(tmp_path, monkeypatch):
    _write_yaml(tmp_path / "docker-compose.yml", "")
    _write_yaml(
        tmp_path / "system-config.yaml",
        """
        ai_models:
          max_tokens_defaults_by_prefix:
            - "not-a-dict"
            - prefix: ""
              max_tokens: 4096
            - prefix: real-model
              max_tokens: 8192
        """,
    )
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    assert system_config.get_max_tokens_default("real-model-x") == 8192
    assert system_config.get_max_tokens_default("not-a-dict") is None


def test_prefix_order_first_match_wins(tmp_path, monkeypatch):
    """Longer prefix should appear earlier in yaml so it wins over shorter."""
    _write_yaml(tmp_path / "docker-compose.yml", "")
    _write_yaml(
        tmp_path / "system-config.yaml",
        """
        ai_models:
          max_tokens_defaults_by_prefix:
            - prefix: claude-sonnet-4
              max_tokens: 64000
            - prefix: claude
              max_tokens: 8192
        """,
    )
    monkeypatch.setattr(system_config, "_project_root", lambda: tmp_path)
    assert system_config.get_max_tokens_default("claude-sonnet-4-5") == 64000
    assert system_config.get_max_tokens_default("claude-3-5-sonnet") == 8192
