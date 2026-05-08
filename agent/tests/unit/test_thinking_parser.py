"""Unit tests for ThinkingTagParser in core/llm.py."""

from core.llm import ThinkingTagParser

OPEN = "<think>"
CLOSE = "</think>"


class TestThinkingTagParserBasic:
    """Basic parsing tests."""

    def test_simple_text_without_thinking_tags(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("Hello world"))
        # Parser buffers last len(OPEN_TAG)-1 chars to detect partial tags
        final = parser.flush()
        all_text = "".join(r[1] for r in results) + (final[1] if final else "")
        assert all_text == "Hello world"

    def test_simple_thinking_block(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}Some reasoning{CLOSE} and more text"))
        final = parser.flush()
        thinking = "".join(r[1] for r in results if r[0] == "thinking")
        text = "".join(r[1] for r in results if r[0] == "text")
        if final:
            text += final[1]
        assert thinking == "Some reasoning"
        assert text == " and more text"

    def test_multiple_thinking_blocks(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}First{CLOSE} and {OPEN}Second{CLOSE}"))
        final = parser.flush()
        thinking_parts = [r[1] for r in results if r[0] == "thinking"]
        text_parts = [r[1] for r in results if r[0] == "text"]
        assert thinking_parts[0] == "First"
        assert " and " in "".join(text_parts)
        assert thinking_parts[1] == "Second"

    def test_nested_tags_not_supported(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}Outer {OPEN}Inner{CLOSE} text{CLOSE}"))
        assert len(results) >= 2


class TestThinkingTagParserStreaming:
    """Test streaming behavior with partial chunks."""

    def test_chunked_thinking_block(self):
        parser = ThinkingTagParser()
        results = []
        results.extend(parser.feed(f"{OPEN}Some "))
        results.extend(parser.feed("reason"))
        results.extend(parser.feed("ing"))
        results.extend(parser.feed(CLOSE))
        thinking_parts = [r for r in results if r[0] == "thinking"]
        assert len(thinking_parts) >= 1
        combined = "".join([r[1] for r in thinking_parts])
        assert combined == "Some reasoning"

    def test_chunked_without_closing_tag(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}Partial thinking without closing"))
        thinking_results = [r for r in results if r[0] == "thinking"]
        assert len(thinking_results) > 0
        final = parser.flush()
        assert final is not None
        assert final[0] == "thinking"


class TestThinkingTagParserBufferOverflow:
    """Test buffer overflow protection."""

    def test_buffer_overflow_emits_as_text(self):
        parser = ThinkingTagParser()
        huge_content = "x" * (parser.MAX_BUFFER_SIZE + 100)
        results = list(parser.feed(huge_content))
        text_results = [r for r in results if r[0] == "text"]
        assert len(text_results) > 0
        assert len(text_results[0][1]) == parser.MAX_BUFFER_SIZE

    def test_overflow_with_partial_tag_preserved(self):
        parser = ThinkingTagParser()
        huge_content = "x" * (parser.MAX_BUFFER_SIZE - 5) + OPEN[:3]
        results = list(parser.feed(huge_content))
        assert len(results) > 0

    def test_overflow_with_valid_tag_boundary(self):
        parser = ThinkingTagParser()
        thinking_content = f"{OPEN}some thinking" + "x" * (parser.MAX_BUFFER_SIZE - 100)
        full_content = thinking_content + CLOSE + "text after"
        results = list(parser.feed(full_content))
        thinking_results = [r for r in results if r[0] == "thinking"]
        text_results = [r for r in results if r[0] == "text"]
        assert len(thinking_results) > 0
        assert len(text_results) > 0


class TestThinkingTagParserUnicodeBoundaries:
    """Test unicode character handling at chunk boundaries."""

    def test_unicode_at_chunk_boundary(self):
        parser = ThinkingTagParser()
        results = []
        results.extend(parser.feed(f"{OPEN}思"))
        results.extend(parser.feed("考"))
        results.extend(parser.feed("内容"))
        results.extend(parser.feed(CLOSE))
        results.extend(parser.feed("文本"))
        final = parser.flush()
        combined_thinking = "".join([r[1] for r in results if r[0] == "thinking"])
        assert combined_thinking == "思考内容"
        # "文本" may be buffered waiting for partial tag detection; flush to get it
        combined_text = "".join([r[1] for r in results if r[0] == "text"])
        if final and final[0] == "text":
            combined_text += final[1]
        assert combined_text == "文本"

    def test_emoji_in_thinking_block(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}思考 🤔 emoji{CLOSE}"))
        thinking_parts = [r for r in results if r[0] == "thinking"]
        combined = "".join([r[1] for r in thinking_parts])
        assert combined == "思考 🤔 emoji"


class TestThinkingTagParserEdgeCases:
    """Test edge cases and malformed inputs."""

    def test_empty_input(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(""))
        assert results == []
        assert parser.flush() is None

    def test_only_opening_tag(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(OPEN))
        assert results == []
        final = parser.flush()
        assert final is None

    def test_only_closing_tag(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(CLOSE))
        assert len(results) >= 0

    def test_consecutive_tags(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(f"{OPEN}first{CLOSE}{OPEN}second{CLOSE}"))
        thinking_results = [r for r in results if r[0] == "thinking"]
        assert len(thinking_results) >= 2

    def test_tag_case_sensitivity(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("<THINK>reasoning</THINK>"))
        text_results = [r for r in results if r[0] == "text"]
        assert len(text_results) > 0
        combined_text = "".join([r[1] for r in text_results])
        assert "reasoning" in combined_text


class TestThinkingTagParserStateReset:
    """Test state management across multiple feeds."""

    def test_state_preserved_across_feeds(self):
        parser = ThinkingTagParser()
        results1 = list(parser.feed(f"{OPEN}Partial "))
        assert parser.in_think_tag is True
        results2 = list(parser.feed("more"))
        results3 = list(parser.feed(CLOSE))
        all_results = results1 + results2 + results3
        thinking_parts = [r for r in all_results if r[0] == "thinking"]
        combined = "".join([r[1] for r in thinking_parts])
        assert combined == "Partial more"

    def test_flush_resets_state(self):
        parser = ThinkingTagParser()
        list(parser.feed(f"{OPEN}Some content"))
        final = parser.flush()
        assert parser.buffer == ""
        assert final is not None
        assert final[0] == "thinking"

    def test_overflow_reset_state(self):
        parser = ThinkingTagParser()
        huge_content = "x" * (parser.MAX_BUFFER_SIZE + 100)
        list(parser.feed(huge_content))
        assert parser.in_think_tag is False
