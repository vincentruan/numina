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

Translate Numina Learning OS content between English and Chinese. This skill covers the full
translation pipeline — from batch seeding to single-item on-demand translation, security
validation, and frontend display logic.

## Quick Orientation

The Learning OS imports ~1,590 knowledge topics from `os-taxonomy` data in English. Each topic
has corresponding `*_zh` fields for Simplified Chinese. Translation is LLM-powered via the
agent module's multi-provider infrastructure (circuit-breaker-aware, provider-agnostic).

**Primary direction:** English → Chinese (the knowledge graph source is English; Chinese
translations serve the child-facing UI).

**Reverse direction (Chinese → English)** is relevant when:
- A topic name originally contains Chinese characters (e.g., `分数加法 Fraction Addition`)
- The user explicitly wants English content from a Chinese source
- Repairing or normalizing bilingual content

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Translation Pipeline                  │
│                                                          │
│  seed_learning_topics.py                                 │
│    ├── seed_topic_translations()  ← batch topics         │
│    └── seed_cluster_translations() ← batch clusters      │
│              │                                           │
│              ▼                                           │
│  apps/agent/services/topic_translate.py                  │
│    ├── translate_topic()          ← single item          │
│    └── validate_assessment_zh()   ← security check       │
│              │                                           │
│              ▼                                           │
│  LLMClient.complete_json()       ← multi-provider LLM   │
│    (OpenAI / Anthropic / Ollama — circuit-breaker-aware) │
│                                                          │
│  Frontend:                                               │
│    useLocalizedTopic() composable  ← prefers *_zh        │
│    Conditional translate button    ← shown only if NULL  │
└─────────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server/apps/agent/services/topic_translate.py` | Core `translate_topic()` function + validation |
| `server/scripts/seed_learning_topics.py` | Batch translation (seed script) with CLI args |
| `server/packages/db/models/learning/topic.py` | `LearningTopic` + `LearningCluster` models with `_zh` fields |
| `server/packages/db/models/learning/path.py` | `LearningPath` model with `name_zh`, `description_zh` |
| `frontend/apps/child/src/composables/useLocalizedTopic.ts` | Display logic: prefers `_zh` when locale=zh |
| `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` | Conditional translate button + on-demand translation |
| `frontend/apps/main/src/pages/ChildLearningMapPage.vue` | Parent map conditional translate button |

---

## Data Model — Translatable Fields

### LearningTopic (`learning_topics`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `name` | `name_zh` | `String(200)` | Topic display name |
| `description` | `description_zh` | `Text` | Topic explanation |
| `evidence` (list) | `evidence_zh_json` | `Text` | JSON-serialized; accessed via `evidence_zh` property (`json_text` mixin) |
| `assessment_prompt` | `assessment_prompt_zh` | `Text` | AI assessment prompt — **must be security-validated** |

### LearningCluster (`learning_clusters`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `subject` + `domain` | `summary_zh` | `Text` | Summary of the knowledge cluster |

### LearningPath (`learning_paths`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `name` | `name_zh` | `String(200)` | Path display name |
| `description` | `description_zh` | `Text` | Path description |

---

## How to Translate

### 1. Batch Translation (Seed Script)

The seed script handles bulk translation of all untranslated content. It's idempotent —
re-running skips already-translated items.

```bash
cd server

# Full batch translate (topics + clusters)
uv run python scripts/seed_learning_topics.py

# Skip translation (re-seed structure only)
uv run python scripts/seed_learning_topics.py --skip-translation

# Force re-translate everything
uv run python scripts/seed_learning_topics.py --force-retranslate

# Custom batch size (default: 50)
uv run python scripts/seed_learning_topics.py --batch-size 100
```

**What happens internally:**

1. Topics with `name_zh IS NULL` are queried, ordered by `centrality DESC` (high-value first)
2. Topics whose English name already contains Chinese characters are skipped
3. Each topic is passed to `translate_topic()` via the configured LLM provider
4. `assessment_prompt_zh` is validated for injection patterns and length; bad results keep English
5. Per-batch commits — if the process crashes, it resumes from where it left off
6. Cluster summaries are translated separately via `seed_cluster_translations()`

**Scale estimate:** ~1,500 topics × ~300-700 tokens each ≈ 0.5M-1M tokens total, ~3-5 yuan, 3-5 minutes.

### 2. Single Topic Translation

For on-demand translation (e.g., a newly added topic, or repairing one bad translation):

```python
from apps.agent.services.topic_translate import translate_topic
from apps.agent.core.config import get_ai_config

topic_dict = {
    "name": "Fraction Addition",
    "description": "Adding fractions with like denominators",
    "evidence": ["Can compute 1/4 + 2/4 = 3/4", "Understands numerator addition"],
    "assessment_prompt": "Ask the student to solve 2/5 + 1/5 and explain their reasoning.",
}

ai_config = get_ai_config()
result = await translate_topic(topic_dict, ai_config)
# result = {
#     "name_zh": "分数加法",
#     "description_zh": "同分母分数的加法运算",
#     "evidence_zh": ["能计算 1/4 + 2/4 = 3/4", "理解分子相加"],
#     "assessment_prompt_zh": "请让学生解答 2/5 + 1/5 并解释他们的推理过程。"
# }
```

### 3. Cluster Translation

Clusters reuse `translate_topic()` with a shaped dict:

```python
result = await translate_topic({
    "name": f"{cluster.subject} - {cluster.domain}",
    "description": cluster.summary or "",
    "evidence": [],
    "assessment_prompt": "",
}, ai_config)

cluster.summary_zh = result["description_zh"]
```

### 4. Learning Path Translation

Paths follow the same pattern. When creating a path, provide both `name` and `name_zh`:

```python
path = path_service.create_path(
    db, family_id=..., child_id=..., created_by=...,
    name="Math Fundamentals",
    name_zh="数学基础",  # optional but recommended
    description="Core math concepts for grade 3",
    description_zh="三年级核心数学概念",
    topic_ids=[...],
)
```

For batch path translation (no built-in function yet), iterate over paths with missing `_zh`:

```python
from packages.db.models.learning.path import LearningPath

untranslated = session.query(LearningPath).filter(
    (LearningPath.name_zh.is_(None)) | (LearningPath.name_zh == "")
).all()

for path in untranslated:
    result = await translate_topic({
        "name": path.name,
        "description": path.description or "",
        "evidence": [],
        "assessment_prompt": "",
    }, ai_config)
    path.name_zh = result.get("name_zh")
    path.description_zh = result.get("description_zh")

session.commit()
```

### 5. Cross-Environment Translation Reuse

**问题：** 翻译结果存在数据库的 `*_zh` 字段中。本地翻译完成后，测试环境和生产环境的
数据库是独立的，不会自动获得这些翻译。需要一个导出/导入机制。

**解决方案：** 将翻译结果导出为 JSON fixture 文件，提交到 git，在目标环境 seed 后导入。

#### 工作流

```
本地开发环境                     git                    测试/生产环境
┌─────────────┐                                       ┌─────────────┐
│ 翻译完成     │──export──→ learning_translations.json ──→ │ seed 后     │
│ (有 AI API) │           (commit to git)              │ --import    │
│             │                                       │ (无需 AI)    │
└─────────────┘                                       └─────────────┘
```

#### 导出翻译（本地，有 AI API key 的环境）

```bash
cd server

# 导出所有翻译到 JSON fixture
uv run python -c "
import json
from pathlib import Path
from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic, LearningCluster

db = SessionLocal()

# Export topic translations
topics = db.query(LearningTopic).filter(
    LearningTopic.name_zh.isnot(None),
    LearningTopic.deprecated == False,
).all()

topic_data = []
for t in topics:
    topic_data.append({
        'topic_key': t.topic_key,
        'name_zh': t.name_zh,
        'description_zh': t.description_zh,
        'evidence_zh': t.evidence_zh or [],
        'assessment_prompt_zh': t.assessment_prompt_zh,
    })

# Export cluster translations
clusters = db.query(LearningCluster).filter(
    LearningCluster.summary_zh.isnot(None),
).all()

cluster_data = []
for c in clusters:
    cluster_data.append({
        'subject': c.subject,
        'domain': c.domain,
        'summary_zh': c.summary_zh,
    })

output = {
    'version': 1,
    'topics': topic_data,
    'clusters': cluster_data,
}

out_path = Path('server/data/learning_translations.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(f'Exported {len(topic_data)} topics, {len(cluster_data)} clusters → {out_path}')
db.close()
"
```

#### 导入翻译（任何环境，无需 AI API key）

```bash
cd server

# 从 fixture 导入翻译（幂等 — 跳过已有翻译的记录）
uv run python -c "
import json
from pathlib import Path
from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic, LearningCluster

fixture = Path('server/data/learning_translations.json')
if not fixture.exists():
    print('No translation fixture found. Run export first.')
    exit(1)

data = json.loads(fixture.read_text())
db = SessionLocal()

# Import topic translations
imported_topics = 0
for entry in data.get('topics', []):
    topic = db.query(LearningTopic).filter(
        LearningTopic.topic_key == entry['topic_key']
    ).first()
    if not topic:
        continue
    # Skip if already translated (idempotent)
    if topic.name_zh:
        continue
    topic.name_zh = entry.get('name_zh')
    topic.description_zh = entry.get('description_zh')
    topic.evidence_zh_json = json.dumps(entry.get('evidence_zh', []), ensure_ascii=False)
    topic.assessment_prompt_zh = entry.get('assessment_prompt_zh')
    imported_topics += 1

# Import cluster translations
imported_clusters = 0
for entry in data.get('clusters', []):
    cluster = db.query(LearningCluster).filter(
        LearningCluster.subject == entry['subject'],
        LearningCluster.domain == entry['domain'],
    ).first()
    if not cluster or cluster.summary_zh:
        continue
    cluster.summary_zh = entry.get('summary_zh')
    imported_clusters += 1

db.commit()
print(f'Imported {imported_topics} topics, {imported_clusters} clusters')
db.close()
"
```

#### 集成到 seed 脚本

在 `seed_learning_topics.py` 的 `main()` 中，`--skip-translation` 时应自动检查 fixture：

```python
# 在 main() 的翻译逻辑中:
if not args.skip_translation:
    # 有 AI key → 在线翻译
    asyncio.run(seed_topic_translations(db, args.data_dir, args.batch_size))
    asyncio.run(seed_cluster_translations(db, get_ai_config()))
else:
    # 跳过在线翻译 → 尝试从 fixture 导入
    import_translations_from_fixture(db)
```

#### 部署流程

| 环境 | 步骤 | 需要 AI key? |
|------|------|-------------|
| **本地开发** | `seed_learning_topics.py`（在线翻译）→ `export` → commit | ✅ |
| **CI/测试** | `seed --skip-translation` → auto-import fixture | ❌ |
| **生产** | `seed --skip-translation` → auto-import fixture | ❌ |

#### Fixture 文件格式

`server/data/learning_translations.json`:

```json
{
  "version": 1,
  "topics": [
    {
      "topic_key": "mt_aPBzD28_mT",
      "name_zh": "三位数",
      "description_zh": "理解三位数由百位、十位和个位组成",
      "evidence_zh": ["能识别百位、十位、个位", "能用数字表示三位数"],
      "assessment_prompt_zh": "请学生解释 345 中每个数字代表多少。"
    }
  ],
  "clusters": [
    {
      "subject": "mathematics",
      "domain": "Number & Operations",
      "summary_zh": "数与运算：加减乘除、分数、小数等基础运算能力"
    }
  ]
}
```

**匹配策略：** topics 按 `topic_key` 匹配（稳定唯一键），clusters 按 `(subject, domain)` 匹配。
不用 `id` 匹配 — 不同环境的 Snowflake ID 不同。

---

## Security: Injection Validation

**Why this matters:** LLM-translated `assessment_prompt_zh` is fed back to the AI during
student assessments. A malicious injection in this field could override the AI's behavior.
Every translated assessment prompt must be validated before saving.

```python
from scripts.seed_learning_topics import has_chinese_chars, has_injection_pattern

# Check if text contains Chinese characters
has_chinese_chars("分数加法")  # True
has_chinese_chars("Math")      # False

# Check for prompt injection patterns
has_injection_pattern("请计算 3 + 5")           # False (normal)
has_injection_pattern("ignore previous instructions")  # True (injection)
has_injection_pattern("іgnore prevіous іnstructіons")  # True (homoglyph attack)
```

**Detected patterns:**
- `ignore (all) previous instructions` (EN/ZH)
- `forget (all) instructions`
- `system:` prefix
- `<|im_start|>` markers
- Homoglyph attacks: ≥3 Cyrillic/Greek characters in text >10 chars

**Rule:** If `has_injection_pattern(prompt_zh)` returns True OR `len(prompt_zh) > 500`,
keep the English original instead of the translated version.

---

## Frontend Conditional Display

The translate button should only appear when translation is actually needed. This prevents
confusing users with a button that does nothing (because content is already translated).

**Logic (same pattern for `LearningTopicPage.vue` and `ChildLearningMapPage.vue`):**

```typescript
const showTranslateButton = computed(() => {
  // 1. Only show in Chinese locale
  if (!locale.value.startsWith('zh')) return false
  // 2. Must have content to translate
  if (!topic.value?.name) return false
  // 3. Skip if name already contains Chinese (bilingual or originally Chinese)
  if (/[一-鿿]/.test(topic.value.name)) return false
  // 4. Skip if already translated
  if (topic.value.name_zh) return false
  return true
})
```

**Display composable** (`useLocalizedTopic`): prefers `_zh` fields when locale starts with `zh`:

```typescript
const displayName = computed(() => {
  if (locale.value.startsWith('zh') && topic.value?.name_zh) {
    return topic.value.name_zh
  }
  return topic.value?.name || ''
})
```

---

## Adding New Translatable Content

When extending the learning system with new content types that need bilingual support,
follow this checklist:

### Database
1. Add `*_zh` field alongside the English field on the model
   - Text content → `mapped_column(Text, nullable=True)`
   - Short names → `mapped_column(String(200), nullable=True)`
   - Lists → use `json_text()` mixin for JSON-in-Text storage
2. Generate Alembic migration with idempotency guard (`_table_exists` / column-exists check)
3. `nullable=True` — untranslated content gracefully falls back to English

### Translation Pipeline
4. If the content is similar to topics (name + description + evidence), reuse `translate_topic()`
   by shaping the data as a topic dict
5. For new content shapes, add a dedicated translation function following the
   `translate_topic()` pattern: build a prompt, call `LLMClient.complete_json()`,
   validate the response
6. Add the new translation to the seed script or a separate batch function
7. Always validate AI-generated prompts with `has_injection_pattern()` + length check

### Frontend
8. Update the display composable/logic to prefer `*_zh` when `locale.startsWith('zh')`
9. Update conditional translate button `v-if` to check the new `*_zh` field
10. Add i18n keys for any new UI text related to translation

### Idempotency
11. Batch functions must skip already-translated items (check `*_zh IS NULL OR = ''`)
12. Per-item commits for fault tolerance — one failure doesn't block the batch
13. Support `--force-retranslate` for quality repair workflows

---

## Debugging Common Issues

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| All content shows in English despite locale=zh | `*_zh` fields are NULL — translation hasn't run | Run `seed_learning_topics.py` without `--skip-translation` |
| Translate button not showing in zh locale | `name_zh` is already populated OR `has_chinese_chars(name)` is True | Check DB: `SELECT name, name_zh FROM learning_topics WHERE id = ...` |
| Translate button showing even after translation | Frontend cache / composable not reading updated data | Clear browser cache; check that the API response includes `name_zh` |
| `assessment_prompt_zh` falls back to English | Injection validation rejected the translation | Check `has_injection_pattern()` — may be a false positive on educational content |
| Batch translation stops midway | LLM rate limit or API error | Check logs for `WARNING: Translation error`; re-run (idempotent, resumes) |
| `evidence_zh` shows as raw JSON string | Missing `json_text()` accessor on the model | Use the `evidence_zh` property (not `evidence_zh_json`) in Python code |
| Cluster summary not translated | `seed_cluster_translations()` not called or cluster `summary_zh` is NULL | Run seed without `--skip-translation`; check `learning_clusters.summary_zh` |

---

## Translation Quality Assurance

After batch translation, spot-check 20-30 topics (3-4 per subject) for quality:

```bash
cd server
# Check a sample of translated topics
uv run python -c "
from packages.db.models.learning.topic import LearningTopic
from packages.db.session import SessionLocal
db = SessionLocal()
topics = db.query(LearningTopic).filter(
    LearningTopic.name_zh.isnot(None),
    LearningTopic.centrality > 0.5,
).order_by(LearningTopic.centrality.desc()).limit(30).all()
for t in topics:
    print(f'{t.subject:15s} | {t.name:40s} | {t.name_zh}')
db.close()
"
```

**Quality criteria:**
- Mathematical terms should be standard (e.g., "分数" for fraction, "加法" for addition)
- Age-appropriate language for children (avoid overly formal or academic phrasing)
- Assessment prompts should be clear instructions, not literal translations
- Evidence items should be concise and understandable

**If quality is poor:** Use `--force-retranslate` after adjusting the AI model or provider,
or manually fix individual topics via the API/UI translate button.

---

## Extending: Reverse Translation (ZH → EN)

The current infrastructure is EN → Chinese only. For reverse translation:

1. Create a new function following `translate_topic()` pattern but with a ZH→EN system prompt
2. The prompt should instruct the LLM to produce natural English, not literal translation
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

---

## Environment Requirements

Translation requires a configured AI provider. The translation pipeline uses the same
`get_ai_config()` as the rest of the agent module:

| Env Var | Purpose | Default |
|---------|---------|---------|
| `AI_PROVIDER` | LLM provider (`openai`, `anthropic`, `ollama`) | `openai` |
| `AI_MODEL_ID` | Model to use | `gpt-4o-mini` |
| `AI_API_KEY` / `OPENAI_API_KEY` | API credentials | (required) |
| `AI_BASE_URL` | Custom API endpoint (for proxies) | (optional) |

**Cost estimate:** ~3-5 yuan for full batch (~1,500 topics). Monitor via your provider's dashboard.
