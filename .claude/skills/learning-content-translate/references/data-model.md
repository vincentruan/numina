# Data Model — Translatable Fields

## LearningTopic (`learning_topics`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `name` | `name_zh` | `String(200)` | Topic display name |
| `description` | `description_zh` | `Text` | Topic explanation |
| `evidence` (list) | `evidence_zh_json` | `Text` | JSON-serialized; accessed via `evidence_zh` property (`json_text` mixin) |
| `assessment_prompt` | `assessment_prompt_zh` | `Text` | AI assessment prompt — **must be security-validated** |

### Notes

- `evidence_zh` is a `json_text()` mixin property — use the property, not the raw `_json` column.
- All `_zh` fields are `nullable=True` — untranslated content falls back to English in the UI.
- `assessment_prompt_zh` requires injection validation before saving (see SKILL.md §Security).

## LearningCluster (`learning_clusters`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `subject` + `domain` | `summary_zh` | `Text` | Summary of the knowledge cluster |

Clusters are translated by shaping `{name: "{subject} - {domain}", description: summary, evidence: [], assessment_prompt: ""}` and using `description_zh` from the result.

## LearningPath (`learning_paths`)

| English Field | Chinese Field | DB Type | Notes |
|---|---|---|---|
| `name` | `name_zh` | `String(200)` | Path display name |
| `description` | `description_zh` | `Text` | Path description |

Paths should provide `_zh` fields at creation time. For batch translation of existing paths, query with `name_zh IS NULL` and iterate with `translate_topic()`.
