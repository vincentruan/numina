# Parallel Translation Pipeline

## Architecture

```
translate-to-package.py
  │
  ├─ Load packages/os_taxonomy/topics.json     ← current translated state
  ├─ Load upstream data/topics.json             ← English source
  ├─ Diff → items_needing_translation[]
  │
  ├─ asyncio.gather(*[translate_one(t) for t in items], semaphore)
  │     └─ translate_topic(topic, ai_config)   ← from topic_translate.py
  │           └─ LLMClient.complete_json()     ← multi-provider
  │
  ├─ Collect results → merge into package structure
  ├─ Write packages/os_taxonomy/topics.json    ← atomic write
  ├─ Write packages/os_taxonomy/clusters.json  ← atomic write
  └─ Write packages/os_taxonomy/dependencies.json
```

## Concurrency

Default: `asyncio.Semaphore(5)` — 5 parallel LLM calls.

| Provider | Recommended concurrency | Notes |
|----------|------------------------|-------|
| OpenAI | 5-10 | Generous rate limits |
| Anthropic | 3-5 | Lower RPM for Claude |
| Ollama (local) | 1-2 | Limited by GPU VRAM |
| DashScope | 3-5 | Similar to OpenAI |

Override: `--concurrency N`

## Error Handling

### Per-item failures

One translation failure does NOT abort the batch:
- Log the error with topic ID + name
- Keep existing translation if available (don't null out)
- If no existing translation, leave `*Zh` fields empty
- Report failed count at end

### Retry strategy

- **Transient errors** (timeout, 429, 5xx): retry up to 3 times with exponential backoff
- **Structural errors** (malformed JSON, missing keys): no retry, log and skip
- **Circuit breaker**: if >50% of items in a batch of 10 fail, pause 30s before continuing

### Crash recovery

The script writes results incrementally:
1. After each successful translation, append to `results` list
2. Every 50 items, write intermediate state to `packages/os_taxonomy/topics.json`
3. On restart, already-translated items are skipped (their `*Zh` fields are non-null)

## Output Merging

### Topic merge rules

For each topic in the merged output:
1. Start with upstream English fields (source of truth for EN)
2. If topic has existing `*Zh` fields in current package AND topic is unchanged → keep existing translations
3. If topic is new or changed → use fresh translation (or leave empty if translation failed)
4. Copy non-translatable fields as-is: `id`, `type`, `subject`, `domain`, `ageRangeStart`, `ageRangeEnd`, `centrality`, `standards`

### Cluster merge rules

Same pattern: English from upstream, `summaryZh` from translation or preserved.

### Metadata

```json
{
  "version": "v1",
  "topicCount": 1590,
  "translatedCount": 1587,
  "lastSyncedAt": "2026-09-28T10:00:00Z",
  "upstreamCommit": "96a7933"
}
```

`translatedCount` = number of topics with all 4 `*Zh` fields non-null.

## Cost Estimation

| Scenario | Topics | Tokens (est.) | Cost (¥) | Time |
|----------|--------|---------------|----------|------|
| Full translate | 1,590 | ~500K-1M | 3-5 | 5-10 min |
| Incremental (10 new) | 10 | ~3K-7K | 0.02-0.05 | 30s |
| Retranslate subject | ~50 | ~15K-35K | 0.1-0.3 | 1-2 min |

Based on gpt-4o-mini pricing. Actual varies by provider and content length.
