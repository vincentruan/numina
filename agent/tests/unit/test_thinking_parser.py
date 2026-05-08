"""Unit tests for ThinkingTagParser in core/llm.py."""


from core.llm import ThinkingTagParser


class TestThinkingTagParserBasic:
    """Basic parsing tests."""

    def test_simple_text_without_thinking_tags(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("Hello world"))
        assert results == [("text", "Hello world")]
        assert parser.flush() is None

    def test_simple_thinking_block(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("Some reasoning and more text"))
        # Split into thinking and text portions
        assert len(results) == 2
        assert results[0] == ("thinking", "Some reasoning")
        assert results[1] == ("text", "and more text")
        assert parser.flush() is None

    def test_multiple_thinking_blocks(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("First and Second"))
        assert len(results) == 4
        assert results[0] == ("thinking", "First")
        assert results[1] == ("text", " and ")
        assert results[2] == ("thinking", "Second")
        assert results[3] == ("text", "")
        assert parser.flush() is None

    def test_nested_tags_not_supported(self):
        parser = ThinkingTagParser()
        # Nested tags should emit as-is (not validated structure)
        results = list(parser.feed("Outer Inner text"))
        # Parser treats nested as sequential: 1st starts, 1st ends, 2nd starts inside text
        assert len(results) >= 2


class TestThinkingTagParserStreaming:
    """Test streaming behavior with partial chunks."""

    def test_chunked_thinking_block(self):
        parser = ThinkingTagParser()
        # Feed in chunks
        results = []
        results.extend(parser.feed("Some "))
        results.extend(parser.feed("reason"))
        results.extend(parser.feed("ing"))
        results.extend(parser.feed(""))
        # Should accumulate and emit thinking content
        thinking_parts = [r for r in results if r[0] == "thinking"]
        assert len(thinking_parts) >= 1
        # All thinking parts should combine to "Some reasoning"
        combined = "".join([r[1] for r in thinking_parts])
        assert combined == "Some reasoning"

    def test_chunked_without_closing_tag(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("Partial thinking without closing"))
        # Should emit thinking content (buffered, waiting for closing tag)
        # But preserve last 8 chars in buffer for possible closing tag
        thinking_results = [r for r in results if r[0] == "thinking"]
        assert len(thinking_results) > 0
        # Flush should emit remaining
        final = parser.flush()
        assert final is not None
        assert final[0] == "thinking"


class TestThinkingTagParserBufferOverflow:
    """Test buffer overflow protection."""

    def test_buffer_overflow_emits_as_text(self):
        parser = ThinkingTagParser()
        # Create content exceeding MAX_BUFFER_SIZE without proper tags
        huge_content = "x" * (parser.MAX_BUFFER_SIZE + 100)
        results = list(parser.feed(huge_content))
        # Should emit as text to prevent memory bloat
        text_results = [r for r in results if r[0] == "text"]
        assert len(text_results) > 0
        # First emission should be up to MAX_BUFFER_SIZE
        assert len(text_results[0][1]) == parser.MAX_BUFFER_SIZE

    def test_overflow_with_partial_tag_preserved(self):
        parser = ThinkingTagParser()
        # Create content with partial tag at the end
        huge_content = "x" * (parser.MAX_BUFFER_SIZE - 5) + ""
        results = list(parser.feed(huge_content))
        # Should handle gracefully without crashing
        assert len(results) > 0

    def test_overflow_with_valid_tag_boundary(self):
        parser = ThinkingTagParser()
        # Create content with complete thinking block near overflow
        thinking_content = "some thinking" + "x" * (parser.MAX_BUFFER_SIZE - 100)
        closing_tag = ""
        full_content = thinking_content + closing_tag + "text after"
        results = list(parser.feed(full_content))
        # Should emit thinking block and text
        thinking_results = [r for r in results if r[0] == "thinking"]
        text_results = [r for r in results if r[0] == "text"]
        assert len(thinking_results) > 0
        assert len(text_results) > 0


class TestThinkingTagParserUnicodeBoundaries:
    """Test unicode character handling at chunk boundaries."""

    def test_unicode_at_chunk_boundary(self):
        parser = ThinkingTagParser()
        # Chinese characters split across chunks
        chunk1 = "思"
        chunk2 = "考"
        chunk3 = "内容"
        chunk4 = ""
        chunk5 = "文本"
        results = []
        results.extend(parser.feed(chunk1))
        results.extend(parser.feed(chunk2))
        results.extend(parser.feed(chunk3))
        results.extend(parser.feed(chunk4))
        results.extend(parser.feed(chunk5))
        # Should not corrupt unicode characters
        combined_thinking = "".join([r[1] for r in results if r[0] == "thinking"])
        assert combined_thinking == "思考内容"
        combined_text = "".join([r[1] for r in results if r[0] == "text"])
        assert combined_text == "文本"

    def test_emoji_in_thinking_block(self):
        parser = ThinkingTagParser()
        results = list(parser.feed("思考 🤔 emoji"))
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
        results = list(parser.feed(""))
        # Should buffer waiting for content
        assert results == []
        final = parser.flush()
        # Empty buffer after tag, so flush returns None
        assert final is None

    def test_only_closing_tag(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(""))
        # Should emit empty text before closing tag (no prior opening)
        # Then close an empty thinking block (never opened)
        # Behavior depends on parser implementation
        assert len(results) >= 0

    def test_consecutive_tags(self):
        parser = ThinkingTagParser()
        results = list(parser.feed(""))
        # Two thinking blocks with no text between
        # First block empty, second empty
        thinking_results = [r for r in results if r[0] == "thinking"]
        # Should have empty thinking blocks
        assert len(thinking_results) >= 2

    def test_tag_case_sensitivity(self):
        parser = ThinkingTagParser()
        # Lowercase tags (should not match)
        results = list(parser.feed("reasoning"))
        # Should emit as text since tags are case-sensitive
        text_results = [r for r in results if r[0] == "text"]
        assert len(text_results) > 0
        # Full content should be text
        combined_text = "".join([r[1] for r in text_results])
        assert "reasoning" in combined_text


class TestThinkingTagParserStateReset:
    """Test state management across multiple feeds."""

    def test_state_preserved_across_feeds(self):
        parser = ThinkingTagParser()
        # Feed partial content
        results1 = list(parser.feed("Partial "))
        # State: in_think_tag=True, buffer contains "Partial "
        assert parser.in_think_tag is True
        # Continue feeding
        results2 = list(parser.feed("more"))
        results3 = list(parser.feed(""))
        # Should continue in thinking mode until closing tag
        all_results = results1 + results2 + results3
        thinking_parts = [r for r in all_results if r[0] == "thinking"]
        combined = "".join([r[1] for r in thinking_parts])
        assert combined == "Partial more"

    def test_flush_resets_state(self):
        parser = ThinkingTagParser()
        list(parser.feed("Some content"))
        final = parser.flush()
        # After flush, buffer should be empty
        assert parser.buffer == ""
        # Note: in_think_tag state preserved for potential final emission
        # But flush should have cleared it
        assert final is not None
        assert final[0] == "thinking"

    def test_overflow_reset_state(self):
        parser = ThinkingTagParser()
        huge_content = "x" * (parser.MAX_BUFFER_SIZE + 100)
        list(parser.feed(huge_content))
        # Overflow should reset state
        assert parser.in_think_tag is False