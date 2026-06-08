"""Test sensitive field redaction in stream events."""

from apps.agent.services.stream_events import (
    SENSITIVE_KEY_WHITELIST,
    SENSITIVE_KEYS,
    EventStreamBuilder,
    redact_sensitive_fields,
)


class TestRedactSensitiveFields:
    """Tests for the redact_sensitive_fields function."""

    def test_non_sensitive_args_unchanged(self):
        """Tool with non-sensitive args streams unmodified."""
        args = {"family_id": "123", "asset_type": "stock", "limit": 10}
        result = redact_sensitive_fields(args)
        assert result == args

    def test_api_key_redacted(self):
        """Tool with api_key field → value replaced with ***REDACTED***."""
        args = {"api_key": "sk-secret123", "query": "SELECT *"}
        result = redact_sensitive_fields(args)
        assert result["api_key"] == "***REDACTED***"
        assert result["query"] == "SELECT *"

    def test_password_redacted(self):
        """Tool with password field → value redacted."""
        args = {"password": "my-password", "username": "admin"}
        result = redact_sensitive_fields(args)
        assert result["password"] == "***REDACTED***"
        assert result["username"] == "admin"

    def test_nested_secret_redacted(self):
        """Tool with nested config.secret → nested value redacted."""
        args = {
            "config": {
                "secret": "hidden-value",
                "endpoint": "https://api.example.com",
            },
            "action": "fetch",
        }
        result = redact_sensitive_fields(args)
        assert result["config"]["secret"] == "***REDACTED***"
        assert result["config"]["endpoint"] == "https://api.example.com"
        assert result["action"] == "fetch"

    def test_nested_token_redacted(self):
        """Tool with nested auth.token → nested value redacted."""
        args = {
            "auth": {
                "token": "bearer-xyz",
                "expires_in": 3600,
            },
        }
        result = redact_sensitive_fields(args)
        assert result["auth"]["token"] == "***REDACTED***"
        assert result["auth"]["expires_in"] == 3600

    def test_keyboard_not_redacted(self):
        """Tool with keyboard field (false positive prevention) → not redacted."""
        args = {"keyboard": "mechanical", "layout": "qwerty"}
        result = redact_sensitive_fields(args)
        assert result["keyboard"] == "mechanical"
        assert result["layout"] == "qwerty"

    def test_passenger_not_redacted(self):
        """Tool with passenger field → not redacted (whitelist)."""
        args = {"passenger": "John Doe", "flight": "UA123"}
        result = redact_sensitive_fields(args)
        assert result["passenger"] == "John Doe"

    def test_case_insensitive_matching(self):
        """Case-insensitive matching: API_KEY and api_key both redacted."""
        args = {"API_KEY": "secret", "api_key": "also-secret"}
        result = redact_sensitive_fields(args)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"

    def test_deep_nesting_truncated(self):
        """Deep nesting (>5 levels) → nested dict truncated with {_truncated: '...'}."""
        # depth=0: root, depth=1: level1, ... depth=5: level5, depth=6: level6 (truncated)
        args = {"level1": {"level2": {"level3": {"level4": {"level5": {"level6": {"secret": "deep"}}}}}}}
        result = redact_sensitive_fields(args)
        # level5 contains level6, which gets truncated at depth=6
        assert result["level1"]["level2"]["level3"]["level4"]["level5"]["level6"] == {"_truncated": "..."}

    def test_empty_dict_returns_empty(self):
        """Empty dict returns empty dict."""
        args = {}
        result = redact_sensitive_fields(args)
        assert result == {}

    def test_multiple_sensitive_fields(self):
        """Multiple sensitive fields all redacted."""
        args = {
            "api_key": "key1",
            "password": "pass1",
            "token": "tok1",
            "secret": "sec1",
            "data": "public",
        }
        result = redact_sensitive_fields(args)
        assert result["api_key"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["secret"] == "***REDACTED***"
        assert result["data"] == "public"


class TestToolCallRedaction:
    """Tests for tool_call method integration with redaction."""

    def test_tool_call_redacts_api_key(self):
        """tool_call event should have api_key redacted in arguments."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_call(
            tool_name="fetch_data",
            arguments={"api_key": "secret-key", "query": "test"},
        )
        data = event.to_dict()
        assert data["tool"]["arguments"]["api_key"] == "***REDACTED***"
        assert data["tool"]["arguments"]["query"] == "test"

    def test_tool_call_redacts_nested_credentials(self):
        """tool_call event should redact nested credentials."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_call(
            tool_name="external_api",
            arguments={
                "credentials": {"username": "user", "password": "pass"},
                "endpoint": "https://api.com",
            },
        )
        data = event.to_dict()
        assert data["tool"]["arguments"]["credentials"] == "***REDACTED***"
        assert data["tool"]["arguments"]["endpoint"] == "https://api.com"

    def test_tool_call_preserves_non_sensitive(self):
        """tool_call event preserves all non-sensitive arguments."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        args = {"family_id": "f1", "limit": 100, "filters": {"type": "asset"}}
        event = builder.tool_call(tool_name="query", arguments=args)
        data = event.to_dict()
        assert data["tool"]["arguments"] == args

    def test_tool_call_with_display_name_and_icon(self):
        """tool_call preserves display_name/icon while redacting args."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_call(
            tool_name="get_asset_allocation",
            arguments={"api_key": "secret"},
            display_name="获取资产配置",
            icon="📊",
            tool_type="data_query",
        )
        data = event.to_dict()
        assert data["tool"]["display_name"] == "获取资产配置"
        assert data["tool"]["icon"] == "📊"
        assert data["tool"]["tool_type"] == "data_query"
        assert data["tool"]["arguments"]["api_key"] == "***REDACTED***"


class TestToolResultRedaction:
    """Tests for tool_result method integration with redaction."""

    def test_tool_result_redacts_dict_data(self):
        """tool_result event should redact sensitive fields in dict data."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data={"api_key": "secret-key", "result": "query executed"},
        )
        data = event.to_dict()
        assert data["result"]["data"]["api_key"] == "***REDACTED***"
        assert data["result"]["data"]["result"] == "query executed"

    def test_tool_result_redacts_nested_secret(self):
        """tool_result event should redact nested secrets in data."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data={
                "response": {"token": "bearer-xyz", "status": "ok"},
                "message": "success",
            },
        )
        data = event.to_dict()
        assert data["result"]["data"]["response"]["token"] == "***REDACTED***"
        assert data["result"]["data"]["response"]["status"] == "ok"

    def test_tool_result_redacts_list_of_dicts(self):
        """tool_result event should redact sensitive fields in list of dicts."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data=[
                {"api_key": "key1", "name": "server1"},
                {"password": "pass1", "name": "server2"},
            ],
        )
        data = event.to_dict()
        assert data["result"]["data"][0]["api_key"] == "***REDACTED***"
        assert data["result"]["data"][0]["name"] == "server1"
        assert data["result"]["data"][1]["password"] == "***REDACTED***"
        assert data["result"]["data"][1]["name"] == "server2"

    def test_tool_result_preserves_non_sensitive_data(self):
        """tool_result event preserves all non-sensitive data."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        result_data = {"family_id": "f1", "count": 100, "items": ["a", "b"]}
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data=result_data,
        )
        data = event.to_dict()
        assert data["result"]["data"] == result_data

    def test_tool_result_handles_string_data(self):
        """tool_result event handles string data without redaction."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data="Task completed successfully",
        )
        data = event.to_dict()
        assert data["result"]["data"] == "Task completed successfully"

    def test_tool_result_handles_none_data(self):
        """tool_result event handles None data."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=True,
            execution_time_ms=100,
            data=None,
        )
        data = event.to_dict()
        assert data["result"]["data"] is None

    def test_tool_result_with_error(self):
        """tool_result event with error preserves error message."""
        builder = EventStreamBuilder(capability_id="chat", task_id="t1")
        event = builder.tool_result(
            tool_id="t1-tool-0001",
            success=False,
            execution_time_ms=50,
            error="Connection timeout",
        )
        data = event.to_dict()
        assert data["result"]["success"] is False
        assert data["result"]["error"] == "Connection timeout"


class TestSensitiveKeyConstants:
    """Tests for SENSITIVE_KEYS and SENSITIVE_KEY_WHITELIST constants."""

    def test_sensitive_keys_contains_expected_keys(self):
        """SENSITIVE_KEYS should contain all expected sensitive field names."""
        expected = ["api_key", "password", "token", "secret", "credential", "private"]
        for key in expected:
            assert key.lower() in SENSITIVE_KEYS

    def test_whitelist_contains_keyboard(self):
        """Whitelist should contain keyboard to prevent false positive."""
        assert "keyboard" in SENSITIVE_KEY_WHITELIST

    def test_whitelist_contains_passenger(self):
        """Whitelist should contain passenger to prevent false positive."""
        assert "passenger" in SENSITIVE_KEY_WHITELIST

    def test_key_exact_match_not_substring(self):
        """'key' should redact standalone but not substring like 'keyboard'."""
        # Standalone 'key' is in SENSITIVE_KEYS
        assert "key" in SENSITIVE_KEYS
        # But 'keyboard' is whitelisted
        assert "keyboard" in SENSITIVE_KEY_WHITELIST
        # So keyboard should not be redacted
        args = {"key": "secret", "keyboard": "device"}
        result = redact_sensitive_fields(args)
        assert result["key"] == "***REDACTED***"
        assert result["keyboard"] == "device"

    def test_sensitive_keys_contains_prompt_fields(self):
        """SENSITIVE_KEYS should contain prompt-related fields to prevent prompt leakage."""
        expected_prompt_fields = [
            "system_prompt",
            "user_context",
            "internal_context",
            "task_description",
            "developer_prompt",
            "original_prompt",
        ]
        for key in expected_prompt_fields:
            assert key in SENSITIVE_KEYS, f"{key} missing from SENSITIVE_KEYS"

    def test_prompt_fields_are_redacted(self):
        """Prompt-related fields in tool arguments must be redacted."""
        args = {
            "system_prompt": "You are an AI assistant...",
            "user_context": "{'family_id': 123}",
            "internal_context": "internal state",
            "task_description": "Original task: ...",
            "developer_prompt": "Developer notes...",
            "original_prompt": "Raw input prompt",
            "normal_field": "should remain",
        }
        result = redact_sensitive_fields(args)
        assert result["system_prompt"] == "***REDACTED***"
        assert result["user_context"] == "***REDACTED***"
        assert result["internal_context"] == "***REDACTED***"
        assert result["task_description"] == "***REDACTED***"
        assert result["developer_prompt"] == "***REDACTED***"
        assert result["original_prompt"] == "***REDACTED***"
        assert result["normal_field"] == "should remain"

    def test_prompt_field_redaction_case_insensitive(self):
        """Prompt field redaction should be case-insensitive (matches existing behavior)."""
        args = {
            "System_Prompt": "secret",
            "USER_CONTEXT": "secret",
        }
        result = redact_sensitive_fields(args)
        assert result["System_Prompt"] == "***REDACTED***"
        assert result["USER_CONTEXT"] == "***REDACTED***"

    def test_prompt_fields_redacted_in_nested_dict(self):
        """Prompt fields nested in tool result data must also be redacted."""
        data = {
            "result": {
                "system_prompt": "leaked prompt",
                "user_context": "leaked context",
                "summary": "safe summary",
            },
        }
        result = redact_sensitive_fields(data)
        assert result["result"]["system_prompt"] == "***REDACTED***"
        assert result["result"]["user_context"] == "***REDACTED***"
        assert result["result"]["summary"] == "safe summary"