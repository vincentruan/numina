"""Word/Character Error Rate calculation for ASR test validation.

Uses jiwer for standard WER/CER computation with proper text normalization:
- CJK text: character-level CER, punctuation stripped
- Non-CJK text: word-level WER, punctuation replaced with spaces to preserve
  word boundaries (e.g. "Numina!I'm" → "Numina I m" not "NuminaIm")

This fixes a bug where the old implementation stripped whitespace along with
punctuation, causing English ASR output like "hi welcome to numina..." to
collapse into a single untokenizable string and score 100% error rate even
when the recognition was nearly perfect.
"""

import re
import unicodedata

import jiwer

# ── Reference texts for ASR validation ─────────────────────────────────────────

REFERENCE_TEXTS = {
    "zh": "你好，欢迎使用 Numina！我是你的家庭资产管家。我能帮你和家人记录、管理与可视化资产负债，让家庭财务一目了然，隐私自留。",
    "en": "Hi, welcome to Numina! I'm your family asset assistant. I help your family track, manage, and visualize assets and liabilities—self-hosted, private, and always under your control.",
}

# ── Text normalization ─────────────────────────────────────────────────────────


def _normalize_cjk(text: str) -> str:
    """Normalize text for CJK character-level CER.

    Strip punctuation/symbols entirely (CJK characters don't need spaces
    as word boundaries), lowercase, preserve existing whitespace.
    """
    chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        # Skip punctuation (P*) and symbols (S*)
        if cat.startswith("P") or cat.startswith("S"):
            continue
        chars.append(ch)
    return "".join(chars).lower()


def _normalize_en(text: str) -> str:
    """Normalize text for English word-level WER.

    Replace punctuation/symbols with spaces (preserving word boundaries
    that punctuation may have joined, e.g. "Numina!I'm" → "Numina I m"),
    lowercase, collapse multiple spaces, strip.
    """
    chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            chars.append(" ")
        else:
            chars.append(ch)
    text = "".join(chars).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_cjk_reference(lang: str) -> bool:
    """Check if a language code refers to a CJK language."""
    return lang in ("zh", "ja", "ko")


# ── WER/CER computation using jiwer ───────────────────────────────────────────

# Map jiwer AlignmentChunk type strings to our display format
_OP_TYPE_MAP = {
    "equal": "equal",
    "substitute": "sub",
    "insert": "ins",
    "delete": "del",
}


def _compute_jiwer_cjk(reference: str, hypothesis: str) -> tuple[
    list[str], list[str], list[jiwer.AlignmentChunk]
]:
    """Compute character-level CER for CJK text."""
    result = jiwer.process_characters(
        _normalize_cjk(reference), _normalize_cjk(hypothesis)
    )
    tokens_ref = result.references[0] if result.references else []
    tokens_hyp = result.hypotheses[0] if result.hypotheses else []
    alignments = result.alignments[0] if result.alignments else []
    return tokens_ref, tokens_hyp, alignments


def _compute_jiwer_en(reference: str, hypothesis: str) -> tuple[
    list[str], list[str], list[jiwer.AlignmentChunk]
]:
    """Compute word-level WER for non-CJK text."""
    result = jiwer.process_words(
        _normalize_en(reference), _normalize_en(hypothesis)
    )
    tokens_ref = result.references[0] if result.references else []
    tokens_hyp = result.hypotheses[0] if result.hypotheses else []
    alignments = result.alignments[0] if result.alignments else []
    return tokens_ref, tokens_hyp, alignments


def compute_wer(reference: str, hypothesis: str) -> dict:
    """Compute word/character error rate with diff-style operations using jiwer.

    - CJK text → character-level CER via ``jiwer.process_characters``
    - Non-CJK text → word-level WER via ``jiwer.process_words``

    Returns:
        {
            "reference_tokens": [str, ...],
            "hypothesis_tokens": [str, ...],
            "ops": [("equal"|"sub"|"ins"|"del", ref_idx_or_none, hyp_idx_or_none), ...],
            "error_count": int,
            "reference_length": int,
            "error_rate": float (0.0 to 1.0+),
            "error_rate_pct": float (percentage, e.g. 12.5),
        }
    """
    is_cjk = is_cjk_reference(_detect_language(reference))

    if is_cjk:
        tokens_ref, tokens_hyp, alignments = _compute_jiwer_cjk(
            reference, hypothesis
        )
    else:
        tokens_ref, tokens_hyp, alignments = _compute_jiwer_en(
            reference, hypothesis
        )

    n = len(tokens_ref)

    # Expand jiwer's chunk-level alignments into individual token-level ops
    # compatible with the existing response schema and frontend display.
    # Each op references a single token index in the corresponding token list.
    ops: list[tuple[str, int | None, int | None]] = []

    for chunk in alignments:
        op_type = _OP_TYPE_MAP.get(chunk.type, chunk.type)
        ref_range = range(chunk.ref_start_idx, chunk.ref_end_idx)
        hyp_range = range(chunk.hyp_start_idx, chunk.hyp_end_idx)

        if op_type == "equal":
            for ri, hi in zip(ref_range, hyp_range, strict=True):
                ops.append(("equal", ri, hi))
        elif op_type == "sub":
            for ri, hi in zip(ref_range, hyp_range, strict=True):
                ops.append(("sub", ri, hi))
            # Handle length mismatch within a substitution chunk
            if len(ref_range) > len(hyp_range):
                for ri in ref_range[len(hyp_range):]:
                    ops.append(("del", ri, None))
            elif len(hyp_range) > len(ref_range):
                for hi in hyp_range[len(ref_range):]:
                    ops.append(("ins", None, hi))
        elif op_type == "ins":
            for hi in hyp_range:
                ops.append(("ins", None, hi))
        elif op_type == "del":
            for ri in ref_range:
                ops.append(("del", ri, None))

    error_count = sum(1 for op, _, _ in ops if op != "equal")

    error_rate = error_count / n if n > 0 else (1.0 if len(tokens_hyp) > 0 else 0.0)

    return {
        "reference_tokens": tokens_ref,
        "hypothesis_tokens": tokens_hyp,
        "ops": ops,
        "error_count": error_count,
        "reference_length": n,
        "error_rate": error_rate,
        "error_rate_pct": round(error_rate * 100, 1) if n > 0 else (100.0 if len(tokens_hyp) > 0 else 0.0),
    }


def _detect_language(text: str) -> str:
    """Detect if text is primarily CJK for tokenization strategy selection."""
    cjk_count = 0
    alpha_count = 0
    for ch in text:
        if ch.isalpha():
            alpha_count += 1
            cp = ord(ch)
            if (
                0x4E00 <= cp <= 0x9FFF
                or 0x3400 <= cp <= 0x4DBF
                or 0x20000 <= cp <= 0x2A6DF
                or 0xF900 <= cp <= 0xFAFF
            ):
                cjk_count += 1
    if alpha_count == 0:
        return "en"
    return "zh" if cjk_count / alpha_count > 0.3 else "en"
