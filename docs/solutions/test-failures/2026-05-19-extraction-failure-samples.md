# Async Agent Result Extraction — Production Sample Diagnostic Protocol (U10)

**Status:** Pending production deploy of PR 1–4 (U1–U9)
**Date:** 2026-05-19 (placeholder; actual sampling occurs 1-3 days post-deploy)
**Decision:** TBD — populate after sampling

## Purpose

Determine whether the SKILL.md prompt content is reaching the LLM as intended.
This is the **R4 conditional trigger**: U11 (skill_loader.py prompt fix) only
runs if this diagnostic confirms the prompt is **not** entering the LLM.

## Procedure

### 1. Wait for production traffic

After PRs 1–4 deploy, let production accumulate at least 1–3 days of audit
records. Each "重新扫描" click on alerts/disposal/spending_leak/allocation
writes one row to `ai_extraction_audits`.

### 2. Pull samples via admin API

```bash
curl -H "Authorization: Bearer <owner-token>" \
  "https://numina.example.com/api/v1/admin/ai-extraction-audit?days=3&limit=100"
```

Or the equivalent SQL query directly:

```sql
SELECT family_id, capability, method, error_msg, answer_excerpt, extracted_at
FROM ai_extraction_audits
WHERE extracted_at >= NOW() - INTERVAL '3 days'
  AND method IN ('failed', 'llm_fallback_hit')
ORDER BY extracted_at DESC
LIMIT 100;
```

### 3. Inspect 5–10 samples

For each row with `method='failed'` or `method='llm_fallback_hit'`:

- Read the `answer_excerpt` field (first 500 chars of LLM output, PII-redacted)
- Search the text for the literal string `STRUCTURED_DATA`
- Note whether the model attempted the convention (with format drift) or
  produced unstructured prose

### 4. Decision

| Observation                                     | U11 Decision |
|-------------------------------------------------|--------------|
| ≥80% of samples mention `STRUCTURED_DATA`       | NO-GO        |
| <50% of samples mention `STRUCTURED_DATA`       | GO           |
| Mixed (50–80%)                                  | Investigate  |

A NO-GO means the prompt is reaching the LLM and the issue is model
compliance — fixed by the existing regex tolerance (U3) + LLM fallback (U4).

A GO means the prompt is being lost somewhere (most likely `skill_loader.py:127`
when `base.prompt = ""` and family override is also empty) — proceed with U11.

## Sample data (to populate)

| Sample | family_id | capability | method | mentions STRUCTURED_DATA? |
|--------|-----------|------------|--------|---------------------------|
| 1 | TBD | TBD | TBD | TBD |
| 2 | TBD | TBD | TBD | TBD |
| 3 | TBD | TBD | TBD | TBD |
| 4 | TBD | TBD | TBD | TBD |
| 5 | TBD | TBD | TBD | TBD |

## Final decision

**Decision:** TBD
**Decided by:** TBD
**Date:** TBD
**Rationale:** TBD

## References

- Plan: `docs/plans/2026-05-19-002-feat-async-agent-task-result-persistence-v2-plan.md` §U10
- Brainstorm: `docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md` §R4
- Skill loader: `server/apps/agent/services/deerflow_adapter/skill_loader.py:127`
