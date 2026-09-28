# Upstream os-taxonomy Sync

## Data Source

Upstream: `git@github.com:withmarbleapp/os-taxonomy.git`
Local clone: `server/data/os-taxonomy/` (auto-managed by `sync-taxonomy.py`)

Override path via `LEARNING_TAXONOMY_DIR` env var.

## Data Files

| File | Items | Translatable? | Key |
|------|-------|---------------|-----|
| `topics.json` | 1,590 | Yes (name, description, evidence, assessmentPrompt) | `id` (e.g. `mt_AzTrT5ySCx`) |
| `clusters.json` | 183 | Yes (summary) | `(subject, domain, ageRangeStart)` composite |
| `dependencies.json` | 3,221 | No (edges only) | `(topicId, prerequisiteId)` |
| `curriculum-standards.json` | 3,261 | No (reference data) | `key` |
| `manifest.json` | metadata | No | — |

## Change Detection Algorithm

`sync-taxonomy.py` compares upstream `data/*.json` against `server/packages/os_taxonomy/*.json`:

### Topics

1. Load upstream topics → index by `id`
2. Load current package topics → index by `id`
3. **New**: topic `id` in upstream but not in package
4. **Modified**: topic `id` in both, but any English field differs:
   - `name`, `description`, `evidence` (array), `assessmentPrompt`
   - NOT `centrality` changes (cosmetic, no retranslation needed)
5. **Removed**: topic `id` in package but not in upstream
6. **Unchanged**: English fields identical → keep existing `*Zh` fields

### Clusters

1. Load upstream clusters → index by `(subject, domain, ageRangeStart)`
2. Load current package clusters → same key
3. **New**: key in upstream but not in package
4. **Modified**: key in both, but `summary` differs
5. **Removed**: key in package but not in upstream

### Dependencies

Copied as-is from upstream — no translation needed. Full replacement.

## Output: Change Summary

```
os-taxonomy sync complete
  Upstream: v1 (1,590 topics, 183 clusters, 3,221 dependencies)
  Changes detected:
    New topics:      12
    Modified topics:  3
    Removed topics:   0
    New clusters:     1
    Modified clusters: 0
    Dependencies:     updated (3,221 edges)
  → Run translate-to-package.py to translate 15 items (12 new + 3 modified)
```

## Schema Compatibility

Upstream provides JSON Schemas in `schema/`:
- `topics.schema.json` — topic fields
- `clusters.schema.json` — cluster fields
- `dependencies.schema.json` — edge fields

The translated package extends upstream schema with optional `*Zh` fields (same camelCase naming: `nameZh`, `descriptionZh`, `evidenceZh`, `assessmentPromptZh`, `summaryZh`).

## Versioning

Package JSON files carry metadata:
```json
{
  "version": "v1",
  "topicCount": 1590,
  "translatedCount": 1590,
  "lastSyncedAt": "2026-09-28T10:00:00Z",
  "upstreamCommit": "96a7933"
}
```

`lastSyncedAt` and `upstreamCommit` track when the package was last synced from upstream.
