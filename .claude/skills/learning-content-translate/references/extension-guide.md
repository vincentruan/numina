# Extension Guide

## Adding New Translatable Content

When extending the learning system with new content types that need bilingual support:

### Database

1. Add `*_zh` field alongside the English field on the model
   - Text content → `mapped_column(Text, nullable=True)`
   - Short names → `mapped_column(String(200), nullable=True)`
   - Lists → use `json_text()` mixin for JSON-in-Text storage
2. Generate Alembic migration with idempotency guard (`_table_exists` / column-exists check)
3. `nullable=True` — untranslated content gracefully falls back to English

### Translation Pipeline

4. If similar to topics (name + description + evidence), reuse `translate_topic()` by shaping the data as a topic dict
5. For new shapes, follow the `translate_topic()` pattern: build prompt → `LLMClient.complete_json()` → validate response
6. Add the new translation to the seed script or a separate batch function
7. Always validate AI-generated prompts with `has_injection_pattern()` + length check

### Frontend

8. Update display composable/logic to prefer `*_zh` when `locale.startsWith('zh')`
9. Update conditional translate button `v-if` to check the new `*_zh` field
10. Add i18n keys for any new UI text related to translation

### Idempotency

11. Batch functions must skip already-translated items (check `*_zh IS NULL OR = ''`)
12. Per-item commits for fault tolerance — one failure doesn't block the batch
13. Support `--force-retranslate` for quality repair workflows

## Reverse Translation (ZH → EN)

The current infrastructure is EN → Chinese only. For reverse translation:

1. Create a new function following `translate_topic()` pattern but with a ZH→EN system prompt
2. Instruct the LLM to produce natural English, not literal translation
3. Preserve mathematical notation and technical terms as-is
4. Add security validation for the English output (injection can flow in either direction)

```python
# Sketch — not yet implemented
async def translate_topic_to_english(topic_zh: dict, ai_config: dict) -> dict:
    """Translate Chinese topic fields to English."""
    system_prompt = """You are a translator specializing in children's education.
    Translate the following Chinese educational content to natural English.
    Preserve mathematical notation. Return JSON with keys: name, description, evidence (array), assessment_prompt.
    """
    # ... same LLMClient.complete_json() pattern as translate_topic()
```

Use cases:
- Topic names originally containing Chinese (e.g., `分数加法 Fraction Addition`)
- Repairing or normalizing bilingual content
- User explicitly wants English from a Chinese source
