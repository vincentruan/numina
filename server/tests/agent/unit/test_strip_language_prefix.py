"""Unit tests for ``strip_language_prefix`` and title-generation helpers."""

import pytest

from apps.agent.services.runtime.run_extras import (
    _text_fallback_title,
    strip_language_prefix,
)


class TestStripLanguagePrefix:
    """``strip_language_prefix`` removes the frontend language directive."""

    def test_english_prefix_stripped(self):
        text = "[LANGUAGE REQUIREMENT] Output language: English.\n帮我看看家庭财务"
        assert strip_language_prefix(text) == "帮我看看家庭财务"

    def test_chinese_prefix_stripped(self):
        text = "[语言要求] 输出语言：中文。\n帮我看一下资产"
        assert strip_language_prefix(text) == "帮我看一下资产"

    def test_no_prefix_unchanged(self):
        text = "正常的用户消息"
        assert strip_language_prefix(text) == text

    def test_empty_string(self):
        assert strip_language_prefix("") == ""

    def test_prefix_only_returns_empty(self):
        text = "[LANGUAGE REQUIREMENT] Output language: English.\n"
        assert strip_language_prefix(text) == ""

    def test_multiple_newlines_after_prefix(self):
        text = "[LANGUAGE REQUIREMENT] Output language: English.\n\n\n帮我看看"
        assert strip_language_prefix(text) == "帮我看看"

    def test_prefix_in_middle_of_text_not_stripped(self):
        # Prefix must be at the start; embedded prefixes are preserved.
        text = "用户消息 [LANGUAGE REQUIREMENT] Output language: English.\n更多内容"
        assert strip_language_prefix(text) == text

    def test_similar_but_not_exact_prefix_unchanged(self):
        text = "[LANGUAGE] English.\nhello"
        assert strip_language_prefix(text) == text


class TestTextFallbackTitleWithPrefix:
    """``_text_fallback_title`` after prefix stripping produces clean titles."""

    def test_long_message_with_english_prefix(self):
        prefixed = (
            "[LANGUAGE REQUIREMENT] Output language: English.\n"
            "帮我看看家庭财务近况，我想快速了解有没有需要关注的变化。"
        )
        clean = strip_language_prefix(prefixed)
        title = _text_fallback_title(clean)
        assert "[LANGUAGE REQUIREMENT]" not in title
        assert title.startswith("帮我看看家庭财务")

    def test_long_message_with_chinese_prefix(self):
        prefixed = "[语言要求] 输出语言：中文。\n帮我看一下家庭资产负债情况"
        clean = strip_language_prefix(prefixed)
        title = _text_fallback_title(clean)
        assert "[语言要求]" not in title
        assert title.startswith("帮我看一下家庭")

    def test_short_message_prefix_stripped(self):
        prefixed = "[LANGUAGE REQUIREMENT] Output language: English.\n你好"
        clean = strip_language_prefix(prefixed)
        title = _text_fallback_title(clean)
        assert title == "你好"
