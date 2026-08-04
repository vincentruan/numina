"""Unit tests for ASR WER/CER calculation using jiwer.

Validates the fix for the bug where English ASR output scored 100% error rate
due to whitespace stripping in text normalization, collapsing multi-word
sentences into a single untokenizable string.
"""
from apps.backend.app.services.asr_wer import (
    REFERENCE_TEXTS,
    compute_wer,
    is_cjk_reference,
)

# ── Language detection ────────────────────────────────────────────────────────


class TestLanguageDetection:
    def test_chinese_detected(self):
        assert is_cjk_reference("zh") is True

    def test_english_not_cjk(self):
        assert is_cjk_reference("en") is False

    def test_japanese_is_cjk(self):
        assert is_cjk_reference("ja") is True

    def test_korean_is_cjk(self):
        assert is_cjk_reference("ko") is True


# ── Chinese CER ───────────────────────────────────────────────────────────────


class TestChineseCER:
    """Chinese text uses character-level CER via process_characters."""

    def test_identical_texts_zero_error(self):
        text = "你好世界"
        result = compute_wer(text, text)
        assert result["error_rate_pct"] == 0.0
        assert result["error_count"] == 0

    def test_typical_asr_output_reasonable_cer(self):
        """Realistic ASR output with minor errors should score well below 50%."""
        ref = REFERENCE_TEXTS["zh"]
        # Simulated ASR output: mostly correct with small errors
        hyp = (
            "你好，欢迎使用 Numina，我是你的家庭资产管家。"
            "我能帮你和家人记录管理，可视化资产负债，"
            "让家庭财务一目了然，隐私自流。"
        )
        result = compute_wer(ref, hyp)
        # Should be well under 50% (the fail threshold)
        assert result["error_rate_pct"] < 50.0, (
            f"CER {result['error_rate_pct']}% too high for mostly-correct output"
        )

    def test_ops_contain_expected_types(self):
        ref = "你好世界"
        hyp = "你好时间"
        result = compute_wer(ref, hyp)
        op_types = {op[0] for op in result["ops"]}
        assert "equal" in op_types
        assert "sub" in op_types

    def test_completely_wrong_text_high_error(self):
        ref = "你好世界"
        hyp = "abcdefgh"
        result = compute_wer(ref, hyp)
        assert result["error_rate_pct"] > 50.0


# ── English WER ──────────────────────────────────────────────────────────────


class TestEnglishWER:
    """English text uses word-level WER via process_words.

    Key fix: punctuation is replaced with spaces (not stripped), preserving
    word boundaries so multi-word sentences tokenize correctly.
    """

    def test_identical_texts_zero_error(self):
        text = "hello world"
        result = compute_wer(text, text)
        assert result["error_rate_pct"] == 0.0

    def test_typical_asr_output_low_error(self):
        """The core bug fix: ASR that correctly recognizes text should NOT
        score 100% error rate just because spaces/punctuation differ."""
        ref = REFERENCE_TEXTS["en"]
        # Simulated ASR output: correct recognition, missing some punctuation
        hyp = (
            "Hi welcome to numena. "
            "I'm your family asset assistant. "
            "I help your family track manage and visualize assets "
            "and liabilities self hosted private and always under your control"
        )
        result = compute_wer(ref, hyp)
        # Should be well under 50% — "numena" vs "numina" is the main error
        assert result["error_rate_pct"] < 50.0, (
            f"WER {result['error_rate_pct']}% — ASR recognized text correctly "
            f"but scored as total failure"
        )

    def test_no_space_collapse_bug(self):
        """Regression test: ASR output without punctuation-adjacent spaces
        should NOT collapse into a single token."""
        ref = "Hello world, how are you?"
        # ASR output joins words without spaces after punctuation
        hyp = "Hello world,how are you"
        result = compute_wer(ref, hyp)
        # Should have multiple tokens, not 1
        assert len(result["reference_tokens"]) > 1
        assert len(result["hypothesis_tokens"]) > 1
        # A sentence that is only missing end punctuation and has one missing
        # word-space boundary should score well below 100%
        assert result["error_rate_pct"] < 100.0

    def test_ops_alignment(self):
        ref = "hello world"
        hyp = "hello word"
        result = compute_wer(ref, hyp)
        op_types = [op[0] for op in result["ops"]]
        assert "equal" in op_types
        assert "sub" in op_types

    def test_empty_hypothesis(self):
        result = compute_wer("hello world", "")
        assert result["error_rate_pct"] == 100.0

    def test_empty_reference(self):
        result = compute_wer("", "hello")
        assert result["error_rate_pct"] == 100.0

    def test_both_empty(self):
        result = compute_wer("", "")
        assert result["error_rate_pct"] == 0.0


# ── Response format compatibility ────────────────────────────────────────────


class TestResponseFormat:
    """Ensure compute_wer returns the same dict structure the router expects."""

    def test_return_keys(self):
        result = compute_wer("hello", "helo")
        expected_keys = {
            "reference_tokens",
            "hypothesis_tokens",
            "ops",
            "error_count",
            "reference_length",
            "error_rate",
            "error_rate_pct",
        }
        assert set(result.keys()) == expected_keys

    def test_ops_tuple_format(self):
        """Each op must be (type, ref_idx_or_None, hyp_idx_or_None)."""
        result = compute_wer("hello world", "helo world")
        for op in result["ops"]:
            assert len(op) == 3
            op_type, ref_idx, hyp_idx = op
            assert op_type in ("equal", "sub", "ins", "del")
            # For 'equal'/'sub': both indices should be present
            # For 'ins': ref_idx is None
            # For 'del': hyp_idx is None
            if op_type == "ins":
                assert ref_idx is None
            elif op_type == "del":
                assert hyp_idx is None

    def test_error_rate_pct_rounded(self):
        """error_rate_pct should be rounded to 1 decimal place."""
        result = compute_wer("hello world foo", "hello world bar")
        assert isinstance(result["error_rate_pct"], float)
        # Check it's rounded to 1 decimal
        assert result["error_rate_pct"] == round(result["error_rate_pct"], 1)
