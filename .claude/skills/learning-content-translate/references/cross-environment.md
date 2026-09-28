# Cross-Environment Translation Transfer

Translation results live in DB `*_zh` fields. Local/dev, CI, and production databases are independent — translations don't auto-sync. The solution: export to JSON fixture, commit to git, import on target environments.

## Workflow

```
本地开发环境                     git                    测试/生产环境
┌─────────────┐                                       ┌─────────────┐
│ 翻译完成     │──export──→ learning_translations.json ──→ │ seed 后     │
│ (有 AI API) │           (commit to git)              │ --import    │
│             │                                       │ (无需 AI)    │
└─────────────┘                                       └─────────────┘
```

## Export (environment with AI API key)

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/export-translations.py
```

Or manually:
```bash
cd server
uv run python -c "
import json
from pathlib import Path
from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic, LearningCluster

db = SessionLocal()

topics = db.query(LearningTopic).filter(
    LearningTopic.name_zh.isnot(None),
    LearningTopic.deprecated == False,
).all()

topic_data = [{
    'topic_key': t.topic_key,
    'name_zh': t.name_zh,
    'description_zh': t.description_zh,
    'evidence_zh': t.evidence_zh or [],
    'assessment_prompt_zh': t.assessment_prompt_zh,
} for t in topics]

clusters = db.query(LearningCluster).filter(LearningCluster.summary_zh.isnot(None)).all()
cluster_data = [{
    'subject': c.subject, 'domain': c.domain, 'summary_zh': c.summary_zh,
} for c in clusters]

output = {'version': 1, 'topics': topic_data, 'clusters': cluster_data}
out_path = Path('server/data/learning_translations.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(f'Exported {len(topic_data)} topics, {len(cluster_data)} clusters → {out_path}')
db.close()
"
```

## Import (any environment, no AI key needed)

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/import-translations.py
```

The import is idempotent — skips records that already have translations.

## Seed Script Integration

In `seed_learning_topics.py`'s `main()`, when `--skip-translation` is set, the seed script should auto-check for the fixture:

```python
if not args.skip_translation:
    asyncio.run(seed_topic_translations(db, args.data_dir, args.batch_size))
    asyncio.run(seed_cluster_translations(db, get_ai_config()))
else:
    import_translations_from_fixture(db)  # auto-import if fixture exists
```

## Deployment Flow

| Environment | Steps | Needs AI key? |
|-------------|-------|---------------|
| **Local dev** | `seed_learning_topics.py` (online translate) → `export` → commit | ✅ |
| **CI / test** | `seed --skip-translation` → auto-import fixture | ❌ |
| **Production** | `seed --skip-translation` → auto-import fixture | ❌ |

## Fixture Format

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

**Matching strategy:** topics by `topic_key` (stable unique key), clusters by `(subject, domain)`. Never by `id` — Snowflake IDs differ across environments.
