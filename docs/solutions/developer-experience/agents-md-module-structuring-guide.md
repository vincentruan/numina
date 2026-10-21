---
title: "AGENTS.md Module Structuring — Scoping, Section Naming, and Content Ownership"
date: 2026-10-09
category: developer-experience
module: documentation
problem_type: developer_experience
component: documentation
severity: medium
tags: [agents-md, ai-agents, context-loading, module-scoping, naming-convention, documentation, developer-experience]
applies_when:
  - Structuring AGENTS.md files in a multi-module monorepo with AI agent workflows
  - Root AGENTS.md exceeds ~150 lines or contains module-specific content
  - Creating new module AGENTS.md files
  - AI agents apply rules from the wrong module
---

# AGENTS.md Module Structuring — Scoping, Section Naming, and Content Ownership

## Context

AGENTS.md files written for human readers tend to grow into long, cross-module documents. A 500-line root AGENTS.md means agents working in a single module load irrelevant context from other modules — wasting context window and causing agents to apply rules from the wrong module.

Specific problems observed:
1. Root AGENTS.md was ~500 lines — agents loaded irrelevant cross-module context
2. Rules appeared in multiple files (duplication)
3. Module AGENTS.md files had inconsistent section names and depths
4. Some modules lacked key sections (invariants, pitfalls)

## Part 1: Content Ownership (Scoping)

### Hierarchy

**Root `AGENTS.md`** (~120 lines max) contains only:
1. Behavioral guidelines (Think Before Coding, Simplicity First, Surgical Changes)
2. Project identity (one-paragraph overview + tech stack table)
3. Cross-cutting conventions (rules applying to ALL modules)
4. Module documentation table (pointers to module AGENTS.md files)

**Module `AGENTS.md`** files follow a standardized template (see Part 2).

### Content Ownership Table

| Content | Lives in |
|---|---|
| Behavioral guidelines | Root only |
| "UI text in Chinese" | Root only |
| "Incremental formatting" rule | Root only |
| Pydantic v2 patterns | `server/apps/backend/AGENTS.md` + `server/apps/agent/AGENTS.md` (acceptable duplication — independent apps) |
| Emoji convention | `frontend/apps/main/AGENTS.md` only |
| Risk control invariants | `server/apps/agent/AGENTS.md` only |
| Alembic migration warning | `server/apps/backend/AGENTS.md` only |
| Dev commands | Each module's own file only |

**Acceptable duplication:** when two modules are truly independent (backend and agent both use Pydantic v2 but deploy separately), duplicating the pattern is better than a cross-module reference.

## Part 2: Module AGENTS.md Template

```markdown
# {module}/AGENTS.md

Module-specific guidance for {one-line description}.
See root `AGENTS.md` for behavioral guidelines and cross-cutting conventions.

## Quality Commands
[bash block with all quality commands for this module]

## Tooling
- **{tool}:** description + config location

## Key Invariants
[Non-negotiable rules — things that must ALWAYS hold in this module]

## Don't Do
[Absolute prohibitions — things AI agents should NEVER do here]

## Common Pitfalls
[Common mistakes developers make when using this module]

## Gotchas
[Implementation-specific oddities or surprising behavior]

## Watch Out
[Runtime/environment-specific warnings]

## Failure Patterns
[Symptom→cause→fix debugging guides]

## Patterns
[Language/framework-specific patterns with examples]

## Links
- Root [`AGENTS.md`](../AGENTS.md)
- Module [`README.md`](./README.md)
```

## Part 3: Section Naming Convention

| Content Type | Section Name | When to Use |
|-------------|-------------|-------------|
| Module-specific invariants | **Key Invariants** | Always start with this. Every module has local invariants |
| Cross-cutting rules | **Cross-Cutting Invariants** | Rare — prefer reference links over inline copies |
| Usage mistakes | **Common Pitfalls** | When developers repeatedly make the same mistakes |
| Implementation quirks | **Gotchas** | Surprising behavior that isn't a mistake or failure |
| Runtime warnings | **Watch Out** | Runtime/environment edge cases (scheduler, background jobs) |
| Debugging guides | **Failure Patterns** | Symptom→cause→fix format (API-heavy modules) |
| Hard rules | **Don't Do** | Absolute prohibitions (import direction, architecture) |

### Reference Links vs. Inline Copies

**Prefer reference links for cross-cutting rules:**

```markdown
## Key Invariants
1. **Router decorator style** — see root [AGENTS.md](../../AGENTS.md) §URL Style
```

**Avoid inline copies** that create maintenance burden when rules change in multiple locations.

### Backward Compatibility

Do not rename existing sections. Match the style already present. This convention guides **new** AGENTS.md files and new sections added to existing files.

> **Update (2026-07-31):** Since this was originally written, additional modules have been added: `server/packages/core`, `server/packages/security`, `server/packages/storage`, `server/packages/db`, `frontend/packages`, `site`, `frontend/apps/child`, `frontend/apps/main`. The naming convention still applies.

## When to Apply

- Adding a new module: create its AGENTS.md from the template before writing code
- Root AGENTS.md exceeds ~150 lines: audit for module-specific content and move it
- An AI agent applies rules from the wrong module: check whether the rule is in the wrong file
- The same rule appears in multiple files: pick one owner and remove duplicates

## Related

- AGENTS.md restructuring spec: `docs/superpowers/specs/2026-04-23-claude-md-restructuring-design.md` (historical; records the earlier `CLAUDE.md`-based system before the migration to `AGENTS.md`)
- Root [`AGENTS.md`](../../AGENTS.md)
