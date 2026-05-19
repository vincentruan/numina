# Async Agent Result Extraction — Production Sample Diagnostic Protocol (U10)

**Status:** Resolved via static analysis (2026-05-19)
**Date:** 2026-05-19
**Decision:** **U11 NO-GO** (skill_loader.py:127 prompt-fix is unnecessary)

## Purpose

Determine whether the SKILL.md prompt content is reaching the LLM as intended.
This is the **R4 conditional trigger**: U11 (skill_loader.py prompt fix) only
runs if this diagnostic confirms the prompt is **not** entering the LLM.

## Resolution: Static analysis short-circuits the sampling

A code-path trace in the agent service makes live production sampling unnecessary
because the brainstorm's hypothesis #5 is structurally impossible:

### Trace

1. `orchestrator.py:348/601` — calls `skill_loader.load(capability)` to get
   `SkillConfig`, but only reads `.thinking`, `.subagent_enabled`, `.plan_mode`.
2. `orchestrator.py:357` — calls `adapter.stream_dispatch(capability, redacted_context, ...)`
   passing only the **capability name** (a string), not `SkillConfig.prompt`.
3. `deerflow_adapter/adapter.py:273` — `_build_message()` constructs the payload
   sent to DeerFlow as `{skill, context, thinking}`. It does NOT include any
   prompt body.
4. DeerFlow harness independently loads `/app/skills/custom/{skill_name}/SKILL.md`
   per `deerflow_config/base/config.yaml:48` (`- /app/skills/custom`).

A grep for `\.prompt\b` outside `skill_loader.py` returns **zero results** in
`apps/agent/`. `SkillConfig.prompt` is dead data — never read by any consumer.

### Implication

The brainstorm's failure-point #5 ("`base.prompt = ""` clears SKILL.md content")
cannot be the cause of empty extraction results: the prompt that enters the LLM
comes from DeerFlow's own SKILL.md loader, not from `SkillConfig.prompt`. The
four `skills/custom/{alerts,disposal,spending_leak,allocation}/SKILL.md` files
all contain `STRUCTURED_DATA` instructions, which DeerFlow loads directly.

### Side observation (out of R4 scope)

Per-family custom prompts (`entry.prompt` at line 127) currently go into
`SkillConfig.prompt` but are silently dropped because nothing reads that field.
This is a real but unrelated bug. Tracked separately if the family-override
feature ever needs to actually function.

## Procedure (deferred — only run if static analysis is later contradicted)

If at any point production data shows the LLM producing answers without
`STRUCTURED_DATA` blocks despite `skills/custom/{capability}/SKILL.md`
containing the directive, run the procedure below to investigate alternative
hypotheses (DeerFlow harness skill-load failure, file packaging in Docker, etc).

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

| Observation                                     | Action                              |
|-------------------------------------------------|-------------------------------------|
| ≥80% of samples mention `STRUCTURED_DATA`       | Confirms current diagnosis (NO-GO)  |
| <50% of samples mention `STRUCTURED_DATA`       | Investigate DeerFlow skill loading  |
| Mixed (50–80%)                                  | Investigate model compliance        |

If `<50%` mention `STRUCTURED_DATA`, do NOT default to U11 (skill_loader.py)
without first confirming DeerFlow's `/app/skills/custom/` directory contents
in production (the file may not be packaged in the Docker image, or the path
may be misconfigured).

## Final decision

**Decision:** U11 NO-GO (skill_loader.py:127 prompt-fix is not needed)
**Decided by:** Static analysis of orchestrator → adapter → DeerFlow path
**Date:** 2026-05-19
**Rationale:** `SkillConfig.prompt` is dead data — never read by any agent
consumer. DeerFlow loads `skills/custom/{capability}/SKILL.md` independently
from its own configured path. The brainstorm's failure-point #5 is
structurally impossible.

## References

- Plan: `docs/plans/2026-05-19-002-feat-async-agent-task-result-persistence-v2-plan.md` §U10
- Brainstorm: `docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md` §R4
- Skill loader: `server/apps/agent/services/deerflow_adapter/skill_loader.py:127`
- Adapter (no prompt sent): `server/apps/agent/services/deerflow_adapter/adapter.py:273`
- DeerFlow skills path: `server/apps/agent/deerflow_config/base/config.yaml:48`

