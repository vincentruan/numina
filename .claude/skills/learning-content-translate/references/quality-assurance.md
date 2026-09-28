# Translation Quality Assurance

## Data Priority

The **JSON package** (`server/packages/os_taxonomy/`) is the source of truth for translated data.
All quality checks read from the package first. The DB is a runtime cache for multi-node cluster
sharing — it's derived from the package via the seed script, not the other way around.

## Coverage & Quality Check

Reads from `packages/os_taxonomy/topics.json` — no DB connection needed:

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/qa-check-translations.py
```

Output includes:
- Overall coverage (translated / total topics and clusters)
- Per-subject breakdown
- Spot-check of top 30 high-centrality topics (EN vs ZH side by side)
- Missing translation warnings for high-value items
- Assessment prompt coverage check

## Quality Criteria

- **Standard math terms** — "分数" for fraction, "加法" for addition, etc.
- **Age-appropriate** — avoid overly formal or academic phrasing for children
- **Assessment prompts** — clear instructions, not literal translations
- **Evidence items** — concise and understandable
- **Age ranges** — content appropriate for the specified age band

## DB Sync Verification

After updating the JSON package, verify the DB matches:

```bash
cd server

# Seed DB from package (idempotent)
uv run python scripts/seed_learning_topics.py --skip-translation

# Spot-check DB against package
uv run python -c "
import json
from pathlib import Path
from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic

pkg = json.loads(Path('packages/os_taxonomy/topics.json').read_text())
db = SessionLocal()

mismatches = 0
for t in pkg['topics'][:50]:
    row = db.query(LearningTopic).filter(LearningTopic.id == t['id']).first()
    if not row:
        print(f'  DB missing: {t[\"id\"]} ({t[\"name\"]})')
        mismatches += 1
    elif row.name_zh != t.get('nameZh'):
        print(f'  Mismatch {t[\"id\"]}: pkg={t.get(\"nameZh\", \"\")[:20]} db={row.name_zh[:20] if row.name_zh else \"NULL\"}')
        mismatches += 1

print(f'Checked 50 topics: {mismatches} mismatches')
db.close()
"
```

## Fixing Poor Quality

1. **Retranslate specific topics:** Update the JSON package, then re-seed DB
   ```bash
   cd server
   # Retranslate by topic ID
   uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
     --topic-ids mt_AzTrT5ySCx,mt_XbGfVhfiUz
   # Sync to DB
   uv run python scripts/seed_learning_topics.py --skip-translation
   ```

2. **Retranslate entire subject:**
   ```bash
   uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
     --subject Computing
   ```

3. **Full retranslate** (after prompt tuning):
   ```bash
   uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py --force
   ```

4. **Manual fix** — edit the JSON package directly for one-off fixes, then re-seed.

## Coverage Check

Verify no untranslated high-value topics remain:

```bash
cd server
uv run python -c "
import json
from pathlib import Path
pkg = json.loads(Path('packages/os_taxonomy/topics.json').read_text())
high_untranslated = [
    t for t in pkg['topics']
    if not t.get('nameZh') and t.get('centrality', 0) > 0.3
]
print(f'{len(high_untranslated)} high-value topics still untranslated')
for t in high_untranslated[:5]:
    print(f'  {t[\"id\"]}  {t[\"subject\"]} / {t[\"name\"]}  (centrality={t[\"centrality\"]:.3f})')
"
```
