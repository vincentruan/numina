# Task 3 Report: Notification Templates

**Status:** DONE_WITH_CONCERNS

**Commit:** `3dd53817` — feat(notification): add 7 templates for new event types

## One-line summary

Created 7 JSON notification templates in `templates/` for the new event types, with two structural adaptations required to match the existing `sender.py` codebase.

## Files created

| File | Template vars | Emojis |
|---|---|---|
| `ai_report_complete.json` | `{task_title}` | 📊 |
| `ai_finance_coach_complete.json` | `{task_title}` | 💡 |
| `ai_wish_advice_complete.json` | `{task_title}` | 🌟 |
| `ai_literacy_report_complete.json` | `{task_title}` | 📖 |
| `chore_completed.json` | `{child_name}`, `{chore_title}` | 👶 |
| `treasure_redeemed.json` | `{child_name}`, `{treasure_title}` | 💎 |
| `wish_redeemed.json` | `{child_name}`, `{wish_title}` | 🎁 |

All files: 2-space indent, UTF-8 raw, trailing newline. Each has 4 top-level keys matching the existing templates (`telegram`, `email`, `feishu`, `webpush`).

## Verification

- **42/42 renders pass**: every template × every channel type (telegram, email_subject, email_body, feishu, webpush_title, webpush_body) succeeds with no KeyError and no unresolved placeholders.
- **Registry coverage**: all 10 event types in `VALID_REMINDER_TYPES` now have a corresponding template on disk (11 total files including the pre-existing 4).

## Deviations from the plan spec

The plan's JSON examples (both in `docs/superpowers/plans/...` and `briefs/task-4-brief.md`) use **flat keys** like `"email_subject"`, `"webpush_title"` — but `sender.render_template()` indexes **nested** keys (`tmpl["email"]["subject"]`, `tmpl["webpush"]["title"]`). Four of the six channel types would `KeyError` on flat-key JSON.

I also changed `<p>...</p>` email_body values to plain text, because `NotificationSender.send_email()` builds `MIMEText(body, "plain")` — recipients would see literal HTML tags otherwise.

These are necessary adaptations for the template format to be compatible with the existing `sender.py`. The plan doc was written before Tasks 1–2 finalized `sender.py`'s indexing logic.

## Concerns

**None for template validity.** The templates are structurally sound and will integrate correctly with Task 5's dispatcher hooks.

**One item to confirm at Task 5 time:** `chore_completed` and `wish_redeemed` share the same `{child_name}` + `{chore_title}`/`{wish_title}` variable names as in the spec. `treasure_redeemed` uses `{treasure_title}` (not `chore_title`). If the Treasure entity in the data model is conceptually a subset of Chores, the naming may deserve a future cleanup — but this does not affect template correctness.
