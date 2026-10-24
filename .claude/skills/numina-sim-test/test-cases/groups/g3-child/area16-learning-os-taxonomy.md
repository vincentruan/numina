# Area 16 — Learning OS taxonomy Beijing localization & curriculum/edge-status UI

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** This branch introduces two intertwined feature sets:
>
> 1. **os-taxonomy-beijing localization** — zh-CN children receive the Beijing
>    knowledge graph (~3,598 topics including China-specific subjects like 语文,
>    道德与法治, 历史) while en-US children keep the original os-taxonomy graph.
>    The backend filters topics by `source_taxonomy` based on `user.language`.
> 2. **Curriculum badge + edge-status chips** — The child topic detail page
>    surfaces a circular "课" badge + warm-yellow callout showing the MOE 2022
>    curriculum standard each topic maps to, and distinguishes machine-generated
>    dependency edges with a dashed border + "AI" badge.
>
> These cases verify the **end-to-end user-visible behavior** of both features.
> Backend loader/dedup/seed infrastructure is tested by the backend pytest suite;
> this area confirms the data reaches the UI correctly.

Auth: child session (`$SID_CHILD`) for C16.1–C16.8; adult session (`$SID`) for
C16.9–C16.10. Routes under `${CHILD_BASE}` and `${BASE}` respectively.

**Prerequisite:** The database must have been seeded with `--source beijing` for
zh-CN users to see curriculum standards. If the seed was not run, C16.1–C16.4
will show no badge (which is the correct fallback — verify no error, then note
"seed not run" in the report).

---

## Curriculum badge & callout (child topic detail page)

Covers plan `2026-10-09-002` U4 (R1–R5, R8). The backend resolves curriculum
standard identifiers at seed time and stores `{key, name, code}` objects; the
frontend renders them on the topic detail page.

### C16.1 Topic with curriculum standard — badge + callout rendered

> **前置:** zh-CN child, DB seeded with Beijing data, 目标 topic 有
> `curriculum_standards` (code ≠ null).

```
# Navigate to a Beijing-sourced topic known to have curriculum standards
# (e.g. a math or chinese topic from the mtc_ set)
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_standards> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c16.1-curriculum-badge.png
```

Assertions:
- [ ] A circular "课" badge appears adjacent to the topic title (`.curriculum-badge` element)
- [ ] Badge text is "课" (the glyph from `t('learning.curriculum.badgeGlyph')`)
- [ ] Badge has a non-empty `aria-label` (from `t('learning.curriculum.ariaLabel')`)
- [ ] A warm-yellow callout renders below the title row (`.curriculum-callout` element)
- [ ] Callout text follows the format `<curriculum name> · <code>` (e.g. `义务教育数学课程标准（2022年版）· S1.NA.02`)
- [ ] Callout text wraps fully (`overflow-wrap: anywhere`) — no clipping on long CJK titles at 375px viewport
- [ ] The title row is a flex layout: title wraps freely, badge does not squash (`flex: 0 0 auto`)
- [ ] `[console]` zero errors

### C16.2 Topic without curriculum standard — no badge, no callout

> Covers AE2 — en-US child or Beijing topic with no standards.

```
# Navigate to a topic with curriculum_standards = null or [] (e.g. an os-taxonomy topic)
bsk navigate ${CHILD_BASE}learning/topic/<topic_without_standards> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] No `.curriculum-badge` element present
- [ ] No `.curriculum-callout` element present
- [ ] Topic title renders normally (no layout regression from the flex row)
- [ ] `[console]` zero errors

### C16.3 Topic with multiple standards — only first shown

```
# Navigate to a topic with ≥2 curriculum_standards entries
bsk navigate ${CHILD_BASE}learning/topic/<topic_multi_standards> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Badge is present (at least one standard has code ≠ null)
- [ ] Callout shows only the **first** standard's `name · code`
- [ ] Second standard's name/code is NOT visible in the callout text
- [ ] `[console]` zero errors

### C16.4 Legacy topic (code: null) — no badge, no callout

> Covers the transient tolerance path: before re-seed, some rows may hold
> bare-string curriculum entries that resolve to `{key: s, name: s, code: null}`.
> The badge must NOT render for these — showing a raw identifier is the
> unreadable form KD-6 rejected.

```
# If testing before re-seed: navigate to any Beijing topic that may have legacy data
# If testing after re-seed: this case passes trivially (all entries have code)
bsk navigate ${CHILD_BASE}learning/topic/<topic_legacy> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] If all curriculum_standards entries have `code: null` → no badge, no callout
- [ ] HTTP 200 returned (no 500 from ResponseValidationError)
- [ ] `[console]` zero errors

---

## Machine-edge chip styling (prerequisite / next-step chips)

Covers plan `2026-10-09-002` U5 (R6, R7, R8). The topic graph API exposes
`review_status` per edge; the frontend renders machine-generated edges with a
dashed border + "AI" suffix badge.

### C16.5 Machine edge — dashed border + AI badge on prerequisite chip

> **前置:** Topic 有至少一个 `review_status="machine"` 的前置依赖。

```
# Navigate to a topic with machine-generated prerequisite edges
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_machine_edge> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c16.5-machine-chip.png
```

Assertions:
- [ ] The "前置" (prerequisites) section renders
- [ ] The machine-edge chip has CSS class `topic-chip--machine` (dashed border via `::before`)
- [ ] An "AI" suffix badge (`.ai-badge`) is visible inside the chip, text = "AI"
- [ ] The chip retains its mastery icon (van-icon) alongside the AI badge — neither signal suppresses the other
- [ ] The chip has an `aria-label` containing "AI suggested" (en-US) or "AI" (zh-CN) — accessible name for the machine-generated relationship
- [ ] Chip opacity is 1 (not faded/disabled-looking)
- [ ] Chip press feedback works (opacity 0.7 on `:active`)
- [ ] Chip tap target height ≥ 44px (min-height: 44px)
- [ ] Click navigates to the prerequisite topic page (`/learning/topic/<id>`)
- [ ] `[console]` zero errors

### C16.6 Reviewed/null edge — solid border, no AI badge

```
# On the same topic page, observe the reviewed/null-status chips
bsk snapshot --session <id>
```

Assertions:
- [ ] Reviewed (`review_status="reviewed"`) chips do NOT have `topic-chip--machine` class
- [ ] Reviewed chips do NOT have an `.ai-badge` element
- [ ] Null (`review_status=null`) chips render identically to reviewed (no machine treatment)
- [ ] Both reviewed and null chips retain their mastery icon and tag type
- [ ] `[console]` zero errors

### C16.7 Machine edge on next-steps (dependents) chips

> Verify the machine treatment applies to both prerequisite and next-step chips.

```
# Navigate to a topic with machine-generated dependent edges
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_machine_dependent> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] The "后续" (next steps) section renders
- [ ] Machine-edge dependent chips have `topic-chip--machine` class + `.ai-badge`
- [ ] Machine dependent chip has the correct `aria-label` with "AI suggested" wording
- [ ] Click on machine dependent chip navigates to the dependent topic
- [ ] `[console]` zero errors

### C16.8 Chip tap target and accessibility compliance

```
# Measure chip dimensions on a topic with both reviewed and machine edges
bsk evaluate --session <id> --expr "JSON.stringify(Array.from(document.querySelectorAll('.topic-chip')).map(el => ({ classes: el.className, height: el.getBoundingClientRect().height, ariaLabel: el.getAttribute('aria-label'), hasAiBadge: !!el.querySelector('.ai-badge') })))"
```

Assertions:
- [ ] Every `.topic-chip` has `height ≥ 44` (meets the 44×44px minimum tap target)
- [ ] Machine chips have a non-empty `aria-label` mentioning "AI"
- [ ] Reviewed/null chips have no `aria-label` override (use default accessible name)
- [ ] `[console]` zero errors

---

## Locale-based topic filtering

Covers plan `2026-10-09-001` R12, R13, R14. The backend filters topics by
`source_taxonomy` based on `user.language`: zh-CN → `beijing`, en-US →
`os-taxonomy`.

### C16.9 zh-CN child sees Beijing knowledge graph

> **前置:** zh-CN child user, DB seeded with both `beijing` and `os-taxonomy` data.

```
# With zh-CN child session, navigate to the learning map
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c16.9-zhcn-learning-map.png
```

Assertions:
- [ ] Learning map loads without errors
- [ ] Topics displayed are from the Beijing taxonomy (look for China-specific subjects like 语文, 道德与法治 if present)
- [ ] No deprecated topics visible (topics with `deprecated=true` are hidden)
- [ ] Topic names display in Chinese (name_zh preferred by `useLocalizedTopic`)
- [ ] `[console]` zero errors

### C16.10 en-US child sees os-taxonomy knowledge graph

> **前置:** en-US child user (or switch the child's language setting to en-US).

```
# With en-US child session, navigate to the learning map
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Learning map loads without errors
- [ ] Topics displayed are from the os-taxonomy source (original 1,590 topics)
- [ ] No Beijing-specific topics (mtc_ prefix) visible
- [ ] Topic names display in English (or LLM-translated Chinese if available)
- [ ] No curriculum badge on any topic (os-taxonomy topics have no curriculum_standards)
- [ ] `[console]` zero errors

### C16.11 Parent dashboard — locale-consistent topic view

> Covers R14 — parent sees the same topic set their child sees.

```
# With adult session (owner role), navigate to the baby/learning overview
bsk navigate ${BASE}baby --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Baby/learning overview loads without errors
- [ ] Child's learning progress shows topics consistent with the child's locale
- [ ] No errors from topic API calls (locale filter applied correctly)
- [ ] `[console]` zero errors

---

## Dark mode rendering

Covers the deferred items from plan `2026-10-09-002` doc-review (P1). The
callout and machine chip have no explicit dark-mode overrides in v1; verify
they remain readable.

### C16.12 Dark mode — curriculum callout readability

```
# Switch to dark mode, then view a topic with curriculum standards
bsk evaluate --session <id> --expr "document.documentElement.setAttribute('data-theme', 'dark'); 'dark-mode-set'"
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_standards> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c16.12-dark-callout.png
```

Assertions:
- [ ] Curriculum callout background is visible against the dark canvas (`#0a1a1a`)
- [ ] Callout border-left is visible (ochre alpha may need adjustment — note if it vanishes)
- [ ] Callout text is readable (sufficient contrast)
- [ ] Curriculum badge circle is visible
- [ ] `[console]` zero errors

### C16.13 Dark mode — machine-edge chip readability

```
# In dark mode, view a topic with machine-generated edges
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_machine_edge> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c16.13-dark-machine-chip.png
```

Assertions:
- [ ] Machine chip dashed border is visible against the dark card surface
- [ ] AI badge text is readable (ochre background + text contrast)
- [ ] Chip is not confused with a disabled control (full opacity maintained)
- [ ] `[console]` zero errors

---

## i18n key completeness

### C16.14 Both locale files define all new keys

> This is a static check — verify the i18n files are complete.

```
bsk evaluate --session <id> --expr "(async () => {
  const zh = await import('${CHILD_BASE}src/i18n/locales/zh-CN.ts'.replace(/^\\//, window.location.origin + '/'));
  // Fallback: check via the mounted app's i18n
  return 'checked';
})()"
```

Alternatively, inspect the source files directly:

```bash
grep -c 'curriculum\|machineEdge' frontend/apps/child/src/i18n/locales/zh-CN.ts
grep -c 'curriculum\|machineEdge' frontend/apps/child/src/i18n/locales/en-US.ts
```

Assertions:
- [ ] `zh-CN.ts` defines `learning.curriculum.badgeGlyph` (should be "课")
- [ ] `zh-CN.ts` defines `learning.curriculum.ariaLabel` (Chinese text)
- [ ] `zh-CN.ts` defines `learning.machineEdge.ariaLabel` (mentions "AI")
- [ ] `zh-CN.ts` defines `learning.machineEdge.aiBadge` (should be "AI")
- [ ] `en-US.ts` defines the same keys with English values
- [ ] No missing-key fallback warnings in console when rendering badge + callout

---

## Quick Reference

| Case | Feature | Route | Role | Key assertion |
|------|---------|-------|------|---------------|
| C16.1 | Curriculum badge + callout | `/learning/topic/:id` | child | "课" badge + `<name> · <code>` callout |
| C16.2 | No standard → no badge | `/learning/topic/:id` | child | Absence of badge/callout |
| C16.3 | Multiple standards | `/learning/topic/:id` | child | Only first standard shown |
| C16.4 | Legacy code:null | `/learning/topic/:id` | child | No badge, HTTP 200 |
| C16.5 | Machine prereq chip | `/learning/topic/:id` | child | Dashed border + AI badge |
| C16.6 | Reviewed/null chip | `/learning/topic/:id` | child | Solid border, no AI badge |
| C16.7 | Machine dependent chip | `/learning/topic/:id` | child | Same treatment on next-steps |
| C16.8 | Tap target + a11y | `/learning/topic/:id` | child | ≥44px height, aria-label |
| C16.9 | zh-CN locale filter | `/learning` | child | Beijing topics only |
| C16.10 | en-US locale filter | `/learning` | child | os-taxonomy topics only |
| C16.11 | Parent locale view | `/baby` | adult | Consistent with child locale |
| C16.12 | Dark mode callout | `/learning/topic/:id` | child | Readable on dark canvas |
| C16.13 | Dark mode machine chip | `/learning/topic/:id` | child | Dashed border visible |
| C16.14 | i18n key completeness | static check | — | Both locales define all keys |
