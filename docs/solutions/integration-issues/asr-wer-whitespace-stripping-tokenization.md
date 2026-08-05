---
date: 2026-08-05
module: backend
problem_type: integration_issue
component: asr
severity: medium
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "English ASR scores 100% WER despite correct recognition"
  - "'hi welcome to numina' becomes 'hiwelcometouninena' — one giant word"
  - "Chinese CER works (character-level comparison doesn't need word boundaries)"
tags:
  - asr-wer
  - text-normalization
  - jiwer
  - tokenization
applies_when:
  - "Custom punctuation stripping removes whitespace, collapsing multi-word sentences"
  - "WER/CER calculation uses single normalization for both CJK and alphabetic scripts"
---

# ASR WER/CER 100% Error Rate from Whitespace Stripping

## Problem
The custom `_strip_punctuation()` function in `asr_wer.py` removed whitespace along with punctuation, collapsing multi-word English sentences into a single untokenizable string. The WER/CER calculation then compared the collapsed string against the reference, producing 100% error rate even for correct recognitions.

## Symptoms
- English ASR output scores 100% WER despite correct recognition
- `'hi welcome to numina'` becomes `'hiwelcometouninena'` — one giant word
- Chinese CER works (character-level comparison doesn't need word boundaries)

## What Didn't Work
- Adjusting the edit-distance threshold — the underlying tokenization was broken
- Only stripping punctuation characters (`.?!`,) — still lost whitespace between words

## Solution
Replace the custom edit-distance implementation with `jiwer`, which provides proper `process_characters` (CJK CER) and `process_words` (English WER) with correct normalization.

**Before** (`server/apps/backend/app/services/asr_wer.py`):
```python
def _strip_punctuation(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text)  # Also strips whitespace!

def calculate_wer(reference: str, hypothesis: str) -> float:
    ref = _strip_punctuation(reference.lower())   # "hi welcome" → "hiwelcome"
    hyp = _strip_punctuation(hypothesis.lower())
    # Edit distance on collapsed strings → 100% error
```

**After**:
```python
import jiwer

def calculate_wer(reference: str, hypothesis: str) -> dict:
    # English: replace punctuation with spaces to preserve word boundaries
    ref_normalized = re.sub(r'[^\w\s]', ' ', reference.lower())
    hyp_normalized = re.sub(r'[^\w\s]', ' ', hypothesis.lower())
    result = jiwer.process_words(ref_normalized, hyp_normalized)
    return {"wer": result.wer, "operations": _expand_chunks(result)}

def calculate_cer(reference: str, hypothesis: str) -> dict:
    # CJK: strip punctuation entirely, character-level comparison
    ref_normalized = re.sub(r'[^一-鿿]', '', reference)
    hyp_normalized = re.sub(r'[^一-鿿]', '', hypothesis)
    result = jiwer.process_characters(ref_normalized, hyp_normalized)
    return {"cer": result.cer, "operations": _expand_chunks(result)}
```

## Why This Works
The key insight is that English WER needs **word-level** comparison (preserving whitespace as word boundaries), while CJK CER needs **character-level** comparison (whitespace is irrelevant). The old code used a single normalization that destroyed word boundaries for English. `jiwer` provides separate `process_words` and `process_characters` functions that handle each case correctly. The fix also expands jiwer's alignment chunks into individual token-level operations for backward-compatible frontend diff display.

## Prevention
- **Use established NLP libraries for text comparison metrics** — WER/CER are well-defined metrics with established implementations. Custom edit-distance code is error-prone for tokenization edge cases.
- **Test with multi-word inputs** — the bug only manifested with English text containing spaces. Single-character CJK text was unaffected.
- **Separate normalization by language** — CJK and alphabetic scripts have fundamentally different tokenization requirements.
