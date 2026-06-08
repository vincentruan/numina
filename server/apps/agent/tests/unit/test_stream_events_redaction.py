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