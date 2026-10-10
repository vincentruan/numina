---
name: learning-content-translate
description: >
  Sync os-taxonomy upstream data, translate learning content EN→ZH in parallel,
  and maintain translated JSON files in server/packages/os_taxonomy/.
  Also manages the os-taxonomy-beijing zh-CN data source (pre-translated,
  curriculum-aligned, no LLM translation needed).
  Covers: upstream git sync, incremental change detection, parallel translation,
  JSON file update, DB seeding, and cross-environment transfer.
  Triggers: "翻译学习", "translate learning", "sync taxonomy", "同步知识图谱",
  "batch translate", "retranslate", "翻译知识点", "incremental update",
  "增量更新", "seed translation", "learning translation", "os-taxonomy",
  "更新taxonomy", "检测变更", "change detection", "翻译知识图谱",
  "beijing taxonomy", "北京知识图谱", "sync beijing".
disable-model-invocation: true
---

# Learning Content Translation & Taxonomy Sync

Maintain the Chinese-localized os-taxonomy data pipeline: pull upstream English data,
detect changes, translate in parallel, and update the translated JSON package.

**Two data sources:**
- **os-taxonomy** (en-US): English knowledge graph, LLM-translated to Chinese. Described below.
- **os-taxonomy-beijing** (zh-CN): Pre-translated, curriculum-aligned Beijing data. No LLM translation needed — data is used directly for zh-CN users. See [§Beijing Taxonomy](#beijing-taxonomy-os-taxonomy-beijing) below.

## ⚠ 每次执行前：同步 os-taxonomy 上游

os-taxonomy 通过 git submodule 管理（路径: `.claude/skills/learning-content-translate/references/os-taxonomy`）。
**每次开发或执行翻译前**必须执行：

```bash
git submodule update --init --remote .claude/skills/learning-content-translate/references/os-taxonomy
```

**Why**: 确保参考最新上游数据，避免基于过时版本做增量翻译。

同步后可用 `--dry-run` 检查变更：

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/sync-taxonomy.py --dry-run
```

## Primary Data Flow

```
git@github.com:withmarbleapp/os-taxonomy.git   ← upstream (English only)
  │
  ▼  git submodule (auto-managed)
.claude/skills/learning-content-translate/references/os-taxonomy/data/*.json
  │
  ▼  change detection (diff against packages/os_taxonomy/)
new / changed topics & clusters                 ← what needs translation
  │
  ▼  parallel translation (asyncio + LLM)
server/packages/os_taxonomy/*.json              ← TRANSLATED SOURCE OF TRUTH
  │
  ▼  seed script (sync to DB for runtime)
Database (learning_topics, learning_clusters)   ← runtime cache for multi-node sharing
```

**Data priority:** The JSON package (`server/packages/os_taxonomy/`) is the **authoritative
source of truth** for translated data. The database is a derived runtime cache — it exists
so multiple app nodes in a cluster can share query results without each loading JSON. All
translation quality checks and coverage reports read from the JSON package, not the DB.

## Key Files

| File | Purpose |
|------|---------|
| `server/packages/os_taxonomy/topics.json` | 1,590 topics with `*Zh` translation fields |
| `server/packages/os_taxonomy/clusters.json` | 183 clusters with `summaryZh` |
| `server/packages/os_taxonomy/dependencies.json` | 3,221 prerequisite edges (no translation) |
| `server/packages/os_taxonomy/__init__.py` | `get_topics()`, `get_clusters()`, `get_dependencies()` |
| `server/apps/agent/services/topic_translate.py` | `translate_topic()` — single-item LLM translation |
| `server/scripts/seed_learning_topics.py` | Batch seed: JSON → DB with translation |

## Workflows

### 1. Full Sync (first-time or major update)

Pull latest upstream, translate everything, write translated JSON files.

```bash
cd server

# Step 1: Ensure upstream submodule is initialized and up to date
git submodule update --init --remote .claude/skills/learning-content-translate/references/os-taxonomy

# Step 2: Translate all topics + clusters → update packages/os_taxonomy/*.json
uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py --force

# Step 3: Seed DB from updated package
uv run python scripts/seed_learning_topics.py --skip-translation
```

### 2. Incremental Update (routine — detect what changed)

Pull upstream, detect new/changed items, translate only those, merge back.

```bash
cd server

# Step 1: Update submodule + detect changes
git submodule update --init --remote .claude/skills/learning-content-translate/references/os-taxonomy
uv run python ../.claude/skills/learning-content-translate/scripts/sync-taxonomy.py --dry-run

# Step 2: Translate only changed/new items → merge into packages/os_taxonomy/*.json
uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py

# Step 3: Seed DB (idempotent — picks up new topics, translates untranslated)
uv run python scripts/seed_learning_topics.py
```

**What gets detected as "changed":**
- New topic ID not in current `packages/os_taxonomy/topics.json`
- English `name`, `description`, `evidence`, or `assessmentPrompt` differs from upstream
- New cluster or cluster `summary` changed
- Dependencies are copied as-is (no translation needed)

**What's preserved:**
- Existing `*Zh` fields for unchanged topics — never re-translate unless `--force`
- Translation metadata (`translatedCount`, `version`)

### 3. Retranslate Specific Items

Force-retranslate selected topics (e.g., after quality fix or prompt tuning).

```bash
cd server

# Retranslate by topic ID
uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
  --topic-ids mt_AzTrT5ySCx,mt_XbGfVhfiUz

# Retranslate by subject
uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
  --subject Computing

# Retranslate all (force)
uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py --force
```

### 4. Change Detection Only (dry run)

See what changed without translating:

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/sync-taxonomy.py --dry-run
```

Output: summary of new topics, modified topics, new clusters, removed items.

### 5. DB ↔ JSON Package Transfer

Move translations between environments via JSON fixture.

→ Full workflow: [cross-environment.md](references/cross-environment.md)
→ Scripts: [`export-translations.py`](scripts/export-translations.py), [`import-translations.py`](scripts/import-translations.py)

## Translation Architecture

```
translate-to-package.py                  ← batch orchestrator
  │
  ├─ asyncio.Semaphore(5)               ← concurrency limit
  │
  ├─ for each topic needing translation:
  │     └─ translate_topic(topic, ai_config)   ← single item + injection validation
  │           └─ LLMClient.complete_json()     ← multi-provider, circuit-breaker-aware
  │
  └─ merge results → packages/os_taxonomy/topics.json
```

**Concurrency:** 5 parallel LLM calls (configurable via `--concurrency`). Rate-limit safe for most providers.

**Injection safety:** `assessment_prompt_zh` validated by `has_injection_pattern()` — if suspicious, keeps English. See [security section below](#security-injection-validation).

## Security: Injection Validation

`assessment_prompt_zh` feeds back to the AI during assessments — must be clean.

**Rule:** If `has_injection_pattern(prompt_zh)` returns True OR `len(prompt_zh) > 500`, keep English.

Detected: `ignore previous instructions` (EN/ZH), `system:` prefix, `<|im_start|>`, homoglyph attacks (≥3 Cyrillic/Greek in >10 char text).

## Data Model

For translatable field tables (Topic, Cluster, Path), see [references/data-model.md](references/data-model.md).

## Upstream Sync Details

→ Change detection algorithm, git sync, schema diffing: [references/os-taxonomy-sync.md](references/os-taxonomy-sync.md)
→ Upstream data lives in submodule: `references/os-taxonomy/`

## Parallel Translation Pipeline

→ Concurrency, error handling, retry strategy: [references/parallel-translation.md](references/parallel-translation.md)

## Adding New Translatable Content

→ Checklist for DB + pipeline + frontend: [references/extension-guide.md](references/extension-guide.md)

## Beijing Taxonomy (os-taxonomy-beijing)

The Beijing data source provides pre-translated, curriculum-aligned zh-CN content.
It replaces the LLM-translation pipeline for Chinese users — zh-CN learners see
Beijing data; en-US learners see the translated os-taxonomy data.

### Data Location

```
server/data/os-taxonomy-beijing/   ← git submodule
  data/
    topics.zh.json          (1,590 mt_ translated topics)
    cn-topics.json           (2,008 mtc_ China-specific topics)
    dependencies.zh.json     (mt_→mt_ edges)
    cn-dependencies.json     (mtc_→mtc_ edges)
    cn-bridge-dependencies.json (mt_→mtc_ bridge edges)
    clusters.zh.json         (topic clusters)
    cn-curriculum-standards.json (MOE 2022 curriculum metadata)
```

### Syncing Beijing Data

```bash
# Update the submodule
git submodule update --remote server/data/os-taxonomy-beijing

# Re-seed the database (applies dedup mapping if present)
cd server
uv run python scripts/seed_learning_topics.py --source beijing
```

→ Full sync workflow: [references/os-taxonomy-beijing-sync.md](references/os-taxonomy-beijing-sync.md)
→ Sync script: [`scripts/sync-beijing-taxonomy.py`](scripts/sync-beijing-taxonomy.py)

### Key Differences from os-taxonomy

| Aspect | os-taxonomy (en) | os-taxonomy-beijing (zh) |
|--------|------------------|--------------------------|
| Translation | LLM-translated EN→ZH | Pre-translated, no LLM needed |
| Curriculum alignment | NGSS / Common Core / UK NC | China MOE 2022 standards |
| China-specific subjects | None | 语文, 道德与法治, 历史 |
| Topic prefixes | `mt_` | `mt_` + `mtc_` (China-specific) |
| Dedup | Not needed | LLM-based dedup merges `mtc_`↔`mt_` overlap |
| Seed command | `--source os-taxonomy` (default) | `--source beijing` |

## Debugging

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Upstream changes not detected | Stale submodule | `git submodule update --init --remote .claude/skills/learning-content-translate/references/os-taxonomy` |
| Translation not appearing in JSON | Script crashed mid-batch | Re-run (idempotent, resumes from last commit) |
| `*Zh` field is null in DB | JSON package has translation but seed skipped | Run seed without `--skip-translation` |
| All English despite locale=zh | `*_zh` fields NULL | Run seed without `--skip-translation` |
| Translate button missing | `name_zh` populated OR name has Chinese | Check DB |
| `assessment_prompt_zh` falls back to English | Injection validation rejected it | Check `has_injection_pattern()` for false positive |
| Batch stops midway | Rate limit / API error | Re-run (idempotent, resumes) |

## Environment Requirements

| Env Var | Purpose | Default |
|---------|---------|---------|
| `AI_PROVIDER` | `openai` / `anthropic` / `ollama` | `openai` |
| `AI_MODEL_ID` | Model | `gpt-4o-mini` |
| `AI_API_KEY` / `OPENAI_API_KEY` | Credentials | (required) |
| `AI_BASE_URL` | Custom endpoint (proxies) | (optional) |
| `LEARNING_TAXONOMY_DIR` | Override upstream data path | `.claude/skills/learning-content-translate/references/os-taxonomy` (submodule) |

## Quality Assurance

→ Spot-check scripts + criteria: [references/quality-assurance.md](references/quality-assurance.md)
