"""Unit tests for workspace.py chat prompt management."""
import tempfile

import pytest

from apps.backend.app.services import workspace


@pytest.fixture
def temp_workspace(monkeypatch):
    """Override WORKSPACE_ROOT to a temp dir for isolation."""
    with tempfile.TemporaryDirectory() as tmp:
        from apps.backend.app.config import settings as s
        monkeypatch.setattr(s, "WORKSPACE_ROOT", tmp)
        yield tmp


def test_get_chat_prompt_returns_none_when_missing(temp_workspace):
    assert workspace.get_chat_prompt("100") is None


def test_save_then_get_chat_prompt_round_trip(temp_workspace):
    content = "你是家庭资产助手。"
    workspace.save_chat_prompt("100", content)
    assert workspace.get_chat_prompt("100") == content


def test_get_chat_prompt_strips_yaml_frontmatter(temp_workspace):
    content = "---\nname: chat\n---\n\n你是家庭资产助手。"
    workspace.save_chat_prompt("100", content)
    body = workspace.get_chat_prompt("100")
    assert body is not None
    assert "你是家庭资产助手。" in body
    assert "name: chat" not in body


def test_delete_chat_prompt_removes_file(temp_workspace):
    workspace.save_chat_prompt("100", "test")
    workspace.delete_chat_prompt("100")
    assert workspace.get_chat_prompt("100") is None


def test_delete_chat_prompt_is_noop_when_missing(temp_workspace):
    workspace.delete_chat_prompt("100")  # should not raise


def test_chat_prompt_isolated_per_family(temp_workspace):
    workspace.save_chat_prompt("100", "family A prompt")
    workspace.save_chat_prompt("200", "family B prompt")
    assert workspace.get_chat_prompt("100") == "family A prompt"
    assert workspace.get_chat_prompt("200") == "family B prompt"
