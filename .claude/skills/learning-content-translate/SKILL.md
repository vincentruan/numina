---
name: learning-content-translate
description: >
  Translate Numina Learning OS content between English and Chinese (bidirectional).
  Covers learning topics, clusters, and learning paths — batch or single-item.
  Use this skill whenever the user asks to translate learning content, run batch translation,
  fix/repair bad translations, add translatable fields to learning models, debug why Chinese
  text isn't showing, or work with the seed script's translation pass.
  Triggers: "翻译学习", "translate learning", "batch translate", "retranslate",
  "翻译知识点", "翻译知识图谱", "learning translation", "seed translation",
  "中文翻译", "Chinese translation", "translate topic", "translate cluster",
  "repair translation", "修复翻译", "name_zh", "description_zh", "summary_zh",
  "翻译学习路径", "translate learning path", "incremental translation".
---

# Learning Content Translation

Translate Numina Learning OS content between English and Chinese. The knowledge graph source
is English (~1,590 topics from `os-taxonomy`); Chinese translations serve the child-facing UI.

**Primary direction:** EN → ZH. **Reverse (ZH → EN):** see [extension-guide §Reverse Translation](references/extension-guide.md#reverse-translation-zh--en).

## Architecture

```
seed_learning_topics.py              ← batch (topics + clusters)
  │
  ▼
topic_translate.translate_topic()    ← single item + security validation
  │
  ▼
LLMClient.complete_json()            ← multi-provider, circuit-breaker-aware
```

Frontend: `useLocalizedTopic()` prefers `*_zh` when `locale.startsWith('zh')`.

## Key Files

| File | Purpose |
|------|---------|
| `server/apps/agent/services/topic_translate.py` | `translate_topic()` + injection validation |
| `server/scripts/seed_learning_topics.py` | Batch seed script with CLI args |
| `server/packages/db/models/learning/topic.py` | Topic/Cluster models with `_zh` fields |
| `server/packages/db/models/learning/path.py` | Path model with `name_zh`, `description_zh` |
| `frontend/apps/child/src/composables/useLocalizedTopic.ts` | Display: prefers `_zh` in zh locale |

## How to Translate

### 1. Batch (seed script)

Idempotent — skips already-translated items. Ordered by `centrality DESC` (high-value first).

```bash
cd server
uv run python scripts/seed_learning_topics.py                    # translate untranslated
uv run python scripts/seed_learning_topics.py --force-retranslate # re-translate all
uv run python scripts/seed_learning_topics.py --skip-translation  # structure only
uv run python scripts/seed_learning_topics.py --batch-size 100    # custom batch (default 50)
```

Internally: topics with `name_zh IS NULL` → `translate_topic()` → `assessment_prompt_zh` validated for injection → per-batch commits (crash-safe). Clusters translated separately via `seed_cluster_translations()`.

~1,500 topics × ~300-700 tokens ≈ 0.5M-1M tokens, ~3-5 yuan, 3-5 min.

### 2. Single Topic

```python
from apps.agent.services.topic_translate import translate_topic
from apps.agent.core.config import get_ai_config

result = await translate_topic({
    "name": "Fraction Addition",
    "description": "Adding fractions with like denominators",
    "evidence": ["Can compute 1/4 + 2/4 = 3/4"],
    "assessment_prompt": "Ask the student to solve 2/5 + 1/5.",
}, get_ai_config())
# → {"name_zh": "分数加法", "description_zh": "...", "evidence_zh": [...], "assessment_prompt_zh": "..."}
```

### 3. Cluster

Reuse `translate_topic()` with shaped dict — result's `description_zh` → `cluster.summary_zh`.

### 4. Learning Path

Provide `name_zh` / `description_zh` at creation time. For batch repair, query paths with `name_zh IS NULL` and iterate with `translate_topic()`.

### 5. Cross-Environment Transfer

Translation results live in DB `*_zh` fields. To move them between environments (local → CI/prod), export to JSON fixture and commit to git.

→ Full workflow: [cross-environment.md](references/cross-environment.md)
→ Scripts: [`export-translations.py`](scripts/export-translations.py), [`import-translations.py`](scripts/import-translations.py)

## Security: Injection Validation

`assessment_prompt_zh` is fed back to the AI during assessments — must be validated before saving.

**Rule:** If `has_injection_pattern(prompt_zh)` returns True OR `len(prompt_zh) > 500`, keep English.

Detected: `ignore previous instructions` (EN/ZH), `system:` prefix, `<|im_start|>`, homoglyph attacks (≥3 Cyrillic/Greek in >10 char text).

```python
from scripts.seed_learning_topics import has_injection_pattern
has_injection_pattern("ignore previous instructions")  # True
has_injection_pattern("请计算 3 + 5")                  # False
```

## Frontend Conditional Display

Translate button only when translation is needed (same pattern in `LearningTopicPage.vue` + `ChildLearningMapPage.vue`):

```typescript
const showTranslateButton = computed(() => {
  if (!locale.value.startsWith('zh')) return false
  if (!topic.value?.name) return false
  if (/[一-鿿]/.test(topic.value.name)) return false  // already bilingual
  if (topic.value.name_zh) return false                // already translated
  return true
})
```

## Data Model

For full translatable field tables (Topic, Cluster, Path), see [references/data-model.md](references/data-model.md).

## Adding New Translatable Content

For the full checklist (DB + pipeline + frontend + idempotency), see [references/extension-guide.md](references/extension-guide.md).

## Debugging

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| All English despite locale=zh | `*_zh` fields NULL | Run seed without `--skip-translation` |
| Translate button missing | `name_zh` populated OR name has Chinese | Check DB |
| Button showing after translation | Frontend cache | Clear cache; check API includes `name_zh` |
| `assessment_prompt_zh` falls back to English | Injection validation rejected it | Check `has_injection_pattern()` for false positive |
| Batch stops midway | Rate limit / API error | Re-run (idempotent, resumes) |
| `evidence_zh` raw JSON | Missing `json_text()` accessor | Use `evidence_zh` property, not `evidence_zh_json` |

## Quality Assurance

→ Spot-check scripts + criteria: [references/quality-assurance.md](references/quality-assurance.md)

## Environment Requirements

| Env Var | Purpose | Default |
|---------|---------|---------|
| `AI_PROVIDER` | `openai` / `anthropic` / `ollama` | `openai` |
| `AI_MODEL_ID` | Model | `gpt-4o-mini` |
| `AI_API_KEY` / `OPENAI_API_KEY` | Credentials | (required) |
| `AI_BASE_URL` | Custom endpoint (proxies) | (optional) |
