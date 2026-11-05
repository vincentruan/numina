"""Test learning MCP tool registration and handler logic.

Task 4 of the learning-tutor SDD: verify 3 MCP tools are registered with
correct metadata and schema, and that the evaluation validation helper
rejects malformed LLM output.
"""

import pytest
from apps.backend.app.services.mcp_tool_registry import (
    TOOL_REGISTRY,
    get_tool,
    validate_registry,
)
from apps.backend.app.services.mcp_session import _validate_evaluation_schema


class TestLearningToolRegistry:
    """Verify 3 learning tools are properly registered."""

    def test_get_learning_topic_registered(self):
        meta = get_tool("get_learning_topic")
        assert meta is not None
        assert meta.name == "get_learning_topic"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "topic_id" in props
        assert "child_id" in props

    def test_get_child_learning_profile_registered(self):
        meta = get_tool("get_child_learning_profile")
        assert meta is not None
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "child_id" in props
        # subject is optional filter
        assert "subject" in props

    def test_record_learning_result_registered(self):
        meta = get_tool("record_learning_result")
        assert meta is not None
        assert meta.requires_write is True  # write operation
        props = meta.input_schema.get("properties", {})
        assert "session_id" in props
        assert "evaluation" in props

    def test_validate_registry_passes(self):
        """Startup validation should not raise."""
        validate_registry()

    def test_tool_names_match_skill_allowed_tools(self):
        """Tool names must match learning-tutor SKILL.md allowed-tools exactly."""
        expected = {
            "get_learning_topic",
            "get_child_learning_profile",
            "record_learning_result",
        }
        registered = {name for name in TOOL_REGISTRY if name in expected}
        assert registered == expected

    def test_get_learning_topic_required_fields(self):
        meta = get_tool("get_learning_topic")
        assert set(meta.input_schema.get("required", [])) == {"topic_id", "child_id"}

    def test_record_learning_result_required_fields(self):
        meta = get_tool("record_learning_result")
        assert set(meta.input_schema.get("required", [])) == {
            "session_id",
            "evaluation",
        }

    def test_all_learning_tools_owner_member_only(self):
        """Learning tools exclude the child role.

        Read-only tools additionally allow external_token (external MCP clients);
        the write tool stays owner/member-only (external write access is gated
        separately by the token's ``allow_write`` flag, not by role).
        """
        for name in (
            "get_learning_topic",
            "get_child_learning_profile",
        ):
            meta = get_tool(name)
            assert meta.allowed_roles == frozenset({"owner", "member", "external_token"})
            assert "child" not in meta.allowed_roles

        write_meta = get_tool("record_learning_result")
        assert write_meta.allowed_roles == frozenset({"owner", "member"})
        assert "child" not in write_meta.allowed_roles
        assert "external_token" not in write_meta.allowed_roles


class TestValidateEvaluationSchema:
    """Verify _validate_evaluation_schema rejects malformed LLM output."""

    def test_valid_evaluation_passes(self):
        evaluation = {
            "evidence_results": [
                {"evidence": "Can count to 10", "met": True},
                {
                    "evidence": "Understands zero",
                    "met": False,
                    "notes": "Still learning",
                },
            ],
            "overall_score": 0.7,
            "recommendation": "keep_learning",
        }
        # Should not raise
        _validate_evaluation_schema(evaluation)

    def test_valid_mastered_passes(self):
        evaluation = {
            "evidence_results": [{"evidence": "Solves addition", "met": True}],
            "overall_score": 1.0,
            "recommendation": "mastered",
        }
        _validate_evaluation_schema(evaluation)

    def test_valid_needs_review_passes(self):
        evaluation = {
            "evidence_results": [],
            "overall_score": 0.3,
            "recommendation": "needs_review",
        }
        _validate_evaluation_schema(evaluation)

    def test_not_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            _validate_evaluation_schema("not a dict")

    def test_missing_evidence_results_raises(self):
        with pytest.raises(ValueError, match="evidence_results"):
            _validate_evaluation_schema(
                {"overall_score": 0.5, "recommendation": "mastered"}
            )

    def test_evidence_results_not_list_raises(self):
        with pytest.raises(ValueError, match="evidence_results"):
            _validate_evaluation_schema(
                {
                    "evidence_results": "not a list",
                    "overall_score": 0.5,
                    "recommendation": "mastered",
                }
            )

    def test_evidence_item_not_dict_raises(self):
        with pytest.raises(ValueError, match=r"evidence_results\[0\]"):
            _validate_evaluation_schema(
                {
                    "evidence_results": ["not a dict"],
                    "overall_score": 0.5,
                    "recommendation": "mastered",
                }
            )

    def test_evidence_item_missing_evidence_field_raises(self):
        with pytest.raises(ValueError, match=r"evidence_results\[0\]"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [{"met": True}],
                    "overall_score": 0.5,
                    "recommendation": "mastered",
                }
            )

    def test_evidence_item_missing_met_field_raises(self):
        with pytest.raises(ValueError, match=r"evidence_results\[0\]"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [{"evidence": "test"}],
                    "overall_score": 0.5,
                    "recommendation": "mastered",
                }
            )

    def test_evidence_item_met_not_bool_raises(self):
        with pytest.raises(ValueError, match=r"evidence_results\[0\]"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [{"evidence": "test", "met": "yes"}],
                    "overall_score": 0.5,
                    "recommendation": "mastered",
                }
            )

    def test_overall_score_missing_raises(self):
        with pytest.raises(ValueError, match="overall_score"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [],
                    "recommendation": "mastered",
                }
            )

    def test_overall_score_out_of_range_raises(self):
        with pytest.raises(ValueError, match="overall_score"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [],
                    "overall_score": 1.5,
                    "recommendation": "mastered",
                }
            )

    def test_overall_score_negative_raises(self):
        with pytest.raises(ValueError, match="overall_score"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [],
                    "overall_score": -0.1,
                    "recommendation": "mastered",
                }
            )

    def test_recommendation_invalid_raises(self):
        with pytest.raises(ValueError, match="recommendation"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [],
                    "overall_score": 0.5,
                    "recommendation": "failed",
                }
            )

    def test_recommendation_missing_raises(self):
        with pytest.raises(ValueError, match="recommendation"):
            _validate_evaluation_schema(
                {
                    "evidence_results": [],
                    "overall_score": 0.5,
                }
            )


class TestTopicGeneratorToolRegistry:
    """Verify 5 new learning-topic-generator tools are registered (Issue #190)."""

    def test_get_taxonomy_topic_registered(self):
        meta = get_tool("get_taxonomy_topic")
        assert meta is not None
        assert meta.name == "get_taxonomy_topic"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "topic_key" in props

    def test_get_taxonomy_dependencies_registered(self):
        meta = get_tool("get_taxonomy_dependencies")
        assert meta is not None
        assert meta.name == "get_taxonomy_dependencies"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "topic_key" in props

    def test_list_taxonomy_topics_registered(self):
        meta = get_tool("list_taxonomy_topics")
        assert meta is not None
        assert meta.name == "list_taxonomy_topics"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "subject" in props
        assert set(meta.input_schema.get("required", [])) == {"subject"}

    def test_validate_question_registered(self):
        meta = get_tool("validate_question")
        assert meta is not None
        assert meta.name == "validate_question"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "topic_id" in props
        assert "question_type" in props
        assert "stem" in props
        assert "answer" in props
        # difficulty should NOT be required (matches actual service signature)
        required = set(meta.input_schema.get("required", []))
        assert "difficulty" not in required

    def test_get_child_weak_points_registered(self):
        meta = get_tool("get_child_weak_points")
        assert meta is not None
        assert meta.name == "get_child_weak_points"
        assert meta.requires_write is False
        props = meta.input_schema.get("properties", {})
        assert "child_id" in props
        assert "limit" in props
        # limit should have a maximum constraint
        limit_schema = props.get("limit", {})
        assert limit_schema.get("maximum") == 100

    def test_all_new_tools_owner_member_external(self):
        """All new tools are read-only and allow external_token."""
        for name in (
            "get_taxonomy_topic",
            "get_taxonomy_dependencies",
            "list_taxonomy_topics",
            "validate_question",
            "get_child_weak_points",
        ):
            meta = get_tool(name)
            assert meta is not None, f"{name} not registered"
            assert meta.allowed_roles == frozenset(
                {"owner", "member", "external_token"}
            ), f"{name} roles mismatch"

    def test_tool_count_total(self):
        """Registry should have 26 tools (21 existing + 5 smart tutor)."""
        assert len(TOOL_REGISTRY) == 26
