---
title: CLAUDE.md Section Naming Convention
date: 2026-05-14
category: developer-experience
problem_type: documentation-standard
severity: low
applies_when:
  - Creating new module CLAUDE.md files
  - Reorganizing documentation structure across server modules
  - Adding invariant or pitfall sections to CLAUDE.md
tags: [documentation, claude-md, naming-convention, module-guidance]
---

# CLAUDE.md Section Naming Convention

## Context

After the Phase 2 server monorepo consolidation, multiple modules (`server/apps/backend`, `server/apps/agent`, `server/apps/scheduler_worker`, `server/packages/domain`) each have their own CLAUDE.md files. These files use different section names for similar content types:

- **backend**: "Key Invariants", "Common Pitfalls", "Failure Patterns"
- **agent**: "Key Invariants (Risk Control)", "Cross-Cutting Invariants", "Gotchas"
- **scheduler_worker**: "Key Invariants", "Don't Do", "Watch Out"
- **packages/domain**: "Key Invariants", "Don't Do"

This inconsistency creates confusion for future contributors. A naming convention ensures clarity while preserving backward compatibility.

## Guidance

### Section Names by Content Type

| Content Type | Recommended Section Name | When to Use |
|-------------|------------------------|-------------|
| **Module-specific invariants** | **Key Invariants** | Invariants that apply only to this module (e.g., backend's "Always run `alembic upgrade head`", agent's "PII redaction") |
| **Cross-cutting rules** | **Cross-Cutting Invariants** | When a module needs to know rules from root CLAUDE.md (use sparingly — prefer reference links instead of inline copies) |
| **Usage mistakes** | **Common Pitfalls** | Common mistakes developers make when using this module (e.g., backend's auth return codes, SnowflakeBase usage) |
| **Implementation quirks** | **Gotchas** | Implementation-specific oddities or surprising behavior (e.g., agent's DeerFlow init failure being non-fatal, `_CHECKPOINTER_LOCK` serialization) |
| **Runtime/environment warnings** | **Watch Out** | Runtime-specific or environment-specific warnings (e.g., scheduler_worker's APScheduler job overlap, Python path requirement for Phase 2 stubs) |
| **Symptom→cause→fix patterns** | **Failure Patterns** | Debugging guides in symptom→cause→fix format (e.g., backend's 307 redirect, JS precision loss) |
| **Hard rules** | **Don't Do** | Absolute prohibitions (e.g., packages/domain's import direction rule, scheduler_worker's "don't create SessionLocal() inside domain services") |

### Reference Links vs. Inline Copies

**Prefer reference links for cross-cutting rules:**

```markdown
## Key Invariants

1. **Router decorator style** — see root [CLAUDE.md](../../CLAUDE.md) §URL Style for the `redirect_slashes=False` rule
```

**Avoid inline copies that create maintenance burden:**

```markdown
## Key Invariants

1. **`redirect_slashes=False`** — `app/main.py` sets this globally. Router root-path decorators must use `""` not `"/"`...
```

**Why:** Cross-cutting rules change over time. If a rule appears in 3+ places, updates may miss one location. Reference links have a single canonical source.

### When to Add a New Section

- **Key Invariants**: Always start with this. Every module has local invariants.
- **Cross-Cutting Invariants**: Use only when the module genuinely needs to know cross-cutting rules and reference links are insufficient (rare).
- **Common Pitfalls**: Add when developers repeatedly make the same mistakes in this module.
- **Gotchas**: Add when the implementation has surprising behavior that isn't a mistake or failure.
- **Watch Out**: Add when runtime or environment edge cases matter (scheduler, background jobs, multi-service dependencies).
- **Failure Patterns**: Add when debugging requires symptom→cause→fix guidance (backend, API-heavy modules).
- **Don't Do**: Add when absolute prohibitions exist (import direction, architecture boundaries).

## Backward Compatibility

**Do not rename existing sections.** The current names (`Gotchas`, `Watch Out`, `Don't Do`) are already in use and have established context. This convention guides **future** CLAUDE.md files and new sections added to existing files.

When adding a new section to an existing CLAUDE.md, match the style already present if it fits the content type. Otherwise, use the recommended name from the table above.

## Examples

### backend/CLAUDE.md (API-heavy module)

```markdown
## Key Invariants

- Always run `alembic upgrade head` before starting...
- Pydantic v2 only — see root CLAUDE.md for rule...

## Common Pitfalls

- Router decorators use "" not "/" — see root CLAUDE.md §URL Style...
- Auth endpoints return 200, not 201...

### Failure Patterns

**JS precision loss / NaN on IDs in the frontend**
- Symptom: frontend receives NaN...
- Cause: response schema inherits from plain BaseModel...
- Fix: inherit from SnowflakeBase...
```

### agent/CLAUDE.md (service with quirky runtime behavior)

```markdown
## Key Invariants (Risk Control)

1. PII redaction — always call pii_redactor.redact()...
2. Policy guard — all requests must pass through policy_guard.check()...

## Gotchas

- DeerFlow init failure is non-fatal — the app starts but DeerFlow calls will fail...
- Temp config dirs accumulate in /tmp — family_adapter_cache creates tempfile.mkdtemp() per family...
```

### packages/domain/CLAUDE.md (shared domain logic)

```markdown
## Key Invariants

1. Import direction — packages/domain must never import from apps/...

## Don't Do

- Don't import from apps/ — import direction rule...
- Don't import across subdomains — audit must not import from device...
```

## Related

- Root [CLAUDE.md](../../CLAUDE.md) — behavioral guidelines and cross-cutting conventions
- [docs/plans/2026-05-14-008-docs-consolidate-duplication-plan.md](../plans/2026-05-14-008-docs-consolidate-duplication-plan.md) — origin of this convention