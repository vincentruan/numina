"""Word/Character Error Rate calculation for ASR test validation.

Computes edit-distance-based error rate between reference and hypothesis text,
returning per-character/word operations for diff-style display.
"""

import unicodedata

# ── Reference texts for ASR validation ─────────────────────────────────────────

REFERENCE_TEXTS = {
    "zh": "你好，欢迎使用 Numina！我是你的家庭资产管家。我能帮你和家人记录、管理与可视化资产负债，让家庭财务一目了然，隐私自留。",
    "en": "Hi, welcome to Numina! I'm your family asset assistant. I help your family track, manage, and visualize assets and liabilities—self-hosted, private, and always under your control.",
}

# ── Text normalization ─────────────────────────────────────────────────────────

# Punctuation to strip (Unicode categories: P* = all punctuation, S* = all symbols)
# Handled via unicodedata.category() in _strip_punctuation() below.


def _strip_punctuation(text: str) -> str:
    """Remove all punctuation, symbols, and whitespace. Keep letters/digits."""
    chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        # Skip punctuation (P*), symbols (S*), separators (Z*)
        if cat.startswith("P") or cat.startswith("S") or cat.startswith("Z"):
            continue
        chars.append(ch)
    return "".join(chars).lower()


def _tokenize(text: str, is_cjk: bool) -> list[str]:
    """Tokenize text for comparison.

    CJK text → character-level tokens.
    Non-CJK text → word-level tokens (split on whitespace after punctuation removal).
    """
    cleaned = _strip_punctuation(text)
    if not cleaned:
        return []
    if is_cjk:
        return list(cleaned)
    return cleaned.split()


def _is_cjk(text: str) -> bool:
    """Detect if text is primarily CJK."""
    cjk_count = 0
    for ch in text:
        cp = ord(ch)
        # CJK Unified Ideographs + extensions
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x20000 <= cp <= 0x2A6DF
            or 0xF900 <= cp <= 0xFAFF
        ):
            cjk_count += 1
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    return cjk_count / len(alpha_chars) > 0.3


# ── Edit distance with ops ─────────────────────────────────────────────────────

def compute_wer(reference: str, hypothesis: str) -> dict:
    """Compute word/character error rate with diff-style operations.

    Returns:
        {
            "reference_tokens": [...],
            "hypothesis_tokens": [...],
            "ops": [("equal"|"sub"|"ins"|"del", ref_idx_or_none, hyp_idx_or_none), ...],
            "error_count": int,
            "reference_length": int,
            "error_rate": float (0.0 to 1.0+),
            "error_rate_pct": float (percentage, e.g. 12.5),
        }
    """
    is_cjk = _is_cjk(reference)
    ref_tokens = _tokenize(reference, is_cjk)
    hyp_tokens = _tokenize(hypothesis, is_cjk)

    n = len(ref_tokens)
    m = len(hyp_tokens)

    if n == 0:
        return {
            "reference_tokens": ref_tokens,
            "hypothesis_tokens": hyp_tokens,
            "ops": [("ins", None, j) for j in range(m)],
            "error_count": m,
            "reference_length": 0,
            "error_rate": float("inf") if m > 0 else 0.0,
            "error_rate_pct": 100.0 if m > 0 else 0.0,
        }

    # DP table
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j - 1],  # substitution
                    dp[i - 1][j],       # deletion
                    dp[i][j - 1],       # insertion
                )

    # Backtrack to recover ops
    ops: list[tuple[str, int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_tokens[i - 1] == hyp_tokens[j - 1]:
            ops.append(("equal", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops.append(("sub", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("del", i - 1, None))
            i -= 1
        else:
            ops.append(("ins", None, j - 1))
            j -= 1

    ops.reverse()

    error_count = sum(1 for op, _, _ in ops if op != "equal")

    return {
        "reference_tokens": ref_tokens,
        "hypothesis_tokens": hyp_tokens,
        "ops": ops,
        "error_count": error_count,
        "reference_length": n,
        "error_rate": error_count / n if n > 0 else 0.0,
        "error_rate_pct": round(error_count / n * 100, 1) if n > 0 else 0.0,
    }


def is_cjk_reference(lang: str) -> bool:
    """Check if a language code refers to a CJK language."""
    return lang in ("zh", "ja", "ko")
