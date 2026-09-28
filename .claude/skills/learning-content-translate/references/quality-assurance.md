# Translation Quality Assurance

## Spot-Check Script

After batch translation, verify 20-30 high-centrality topics (3-4 per subject):

```bash
cd server
uv run python ../.claude/skills/learning-content-translate/scripts/qa-check-translations.py
```

Or manually:
```bash
cd server
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

## Quality Criteria

- **Standard math terms** — "分数" for fraction, "加法" for addition, etc.
- **Age-appropriate** — avoid overly formal or academic phrasing for children
- **Assessment prompts** — clear instructions, not literal translations
- **Evidence items** — concise and understandable

## Fixing Poor Quality

- `--force-retranslate` after adjusting the AI model or provider
- Manual fix via the API/UI translate button for individual topics
- For systemic issues, adjust the system prompt in `translate_topic()`

## Coverage Check

Verify no untranslated high-value topics remain:

```python
from packages.db.models.learning.topic import LearningTopic
from packages.db.session import SessionLocal
db = SessionLocal()
count = db.query(LearningTopic).filter(
    LearningTopic.name_zh.is_(None),
    LearningTopic.deprecated == False,
    LearningTopic.centrality > 0.3,
).count()
print(f'{count} high-value topics still untranslated')
db.close()
```
