---
date: 2026-08-05
module: agent
problem_type: integration_issue
component: deerflow_adapter
severity: medium
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "Session titles show raw thinking blocks like [{'type':'thinking','thinking':'...'}] instead of summaries"
  - "Python list-literal repr appears in the chat history sidebar"
  - "Suggestion generation also receives contaminated thinking content"
tags:
  - thinking-block
  - llm-content
  - structured-output
  - title-generation
applies_when:
  - "LLM structured content blocks (thinking + text) leak into downstream string consumers"
  - "str() called on LLM response.content list produces Python repr instead of human-readable text"
---

# Thinking-Block Content Leaking into Session Titles

## Problem
LLM models with thinking (Claude extended thinking, Qwen3) return `response.content` as a list of dicts: `[{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]`. When `str()` is called on this list for title generation, the result is a Python repr like `[{'signature': '', 'thinking': '...'}]` — raw thinking block data becomes the session title.

## Symptoms
- Session titles show `[{'signature': '', 'thinking': 'Let me analyze...'}]` instead of human-readable summaries
- Python list-literal repr appears in the chat history sidebar
- Suggestion generation also receives contaminated thinking content

## What Didn't Work
- Checking for `[SKILL:` prefix only — old fallback detection missed the new thinking-block repr pattern
- Stripping at a single write path — multiple code paths (`threads.update_thread_state`, `patch_thread`, `agent_dispatch._persist_session_metadata`) all write titles independently

## Solution
Add `_strip_thinking_from_text` and `_extract_text_from_content_blocks` helpers, then apply them at ALL title/suggestion write paths. Also detect Python list-literal repr in `_is_fallback_title`.

**Before** (`server/apps/agent/services/runtime/run_extras.py`):
```python
# Title was extracted by calling str() on the content directly
title = str(response.content)  # Produces "[{'type': 'thinking', ...}]"
```

**After**:
```python
def _extract_text_from_content_blocks(content: Any) -> str:
    """Extract only text portions from structured LLM output."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type", "") == "thinking":
                    continue  # skip thinking blocks entirely
                text_val = block.get("text") or block.get("content")
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
        return " ".join(parts) if parts else str(content)
    return str(content)

def _strip_thinking_from_text(text: str) -> str:
    """Remove <think>...</think> blocks from text."""
    import re
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

## Why This Works
The `_extract_text_from_content_blocks` function walks the structured content list and only concatenates `text`/`content` fields from non-thinking blocks. The `_strip_thinking_from_text` function handles the case where thinking is embedded as XML-style `<think>` tags within a text string. By applying both at every title write path (defense in depth), thinking content never reaches the user-visible title field.

## Prevention
- **Always use structured content extraction** when consuming LLM responses — never `str()` on content blocks that may contain thinking/reasoning data.
- **Apply sanitization at every write path** — the bug recurred because fixing one path (e.g., `update_thread_state`) didn't prevent the same contamination through `patch_thread` or `_persist_session_metadata`.
- **Test with thinking-enabled models** — the bug only manifests with models that return structured content blocks.
