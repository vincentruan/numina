# Cross-Environment Translation Transfer

## Data Priority

The **JSON package** (`server/packages/os_taxonomy/`) is the source of truth.
It's committed to git, so all environments get translations by pulling the repo.

The DB is a **runtime cache** for multi-node cluster sharing. It's populated from
the JSON package via `seed_learning_topics.py --skip-translation`.

## Primary Flow: Git-based Sync (recommended)

```
Developer machine                          git                    All environments
┌───────────────────┐                                           ┌───────────────────┐
│ translate-to-     │──commit──→ packages/os_taxonomy/*.json ──→ │ seed script       │
│ package.py        │           (committed to repo)             │ loads JSON → DB   │
│ (has AI API key)  │                                           │ (no AI needed)    │
└───────────────────┘                                           └───────────────────┘
```

**Steps:**
1. Developer runs `translate-to-package.py` → updates JSON files
2. Commit `packages/os_taxonomy/*.json` to git
3. All environments pull the updated files
4. Seed script loads JSON into DB: `seed_learning_topics.py --skip-translation`

No separate export/import needed — the JSON files ARE the transfer format.

## Legacy Flow: DB Fixture Export/Import

Only needed when:
- Translations exist only in DB (old data before JSON package was source of truth)
- Migrating from one DB to another without going through git

→ Scripts: [`export-translations.py`](scripts/export-translations.py), [`import-translations.py`](scripts/import-translations.py)

### Export (from environment with AI API key)

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/export-translations.py
```

### Import (any environment, no AI key needed)

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/import-translations.py
```

The import is idempotent — skips records that already have translations.

## Deployment Flow

| Environment | Steps | Needs AI key? |
|-------------|-------|---------------|
| **Local dev** | `translate-to-package.py` → commit → seed | ✅ (for translation only) |
| **CI / test** | `git pull` → `seed --skip-translation` | ❌ |
| **Production** | `git pull` → `seed --skip-translation` | ❌ |

## JSON Package Format

`server/packages/os_taxonomy/topics.json`:
```json
{
  "version": "v1",
  "topicCount": 1590,
  "translatedCount": 1590,
  "lastSyncedAt": "2026-09-28T10:00:00Z",
  "upstreamCommit": "96a7933",
  "topics": [
    {
      "id": "mt_AzTrT5ySCx",
      "name": "AI in Daily Life",
      "description": "...",
      "nameZh": "日常生活中的AI",
      "descriptionZh": "...",
      "evidenceZh": ["..."],
      "assessmentPromptZh": "..."
    }
  ]
}
```

Matching is by `id` (stable upstream identifier). Never by Snowflake DB id.
