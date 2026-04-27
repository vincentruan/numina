---
title: CLAUDE.md Files Should Be Scoped to Module Consumers, Not Human Readers
date: 2026-04-27
category: docs/solutions/developer-experience
module: documentation
problem_type: developer_experience
component: documentation
severity: medium
applies_when:
  - Structuring CLAUDE.md files in a multi-module monorepo with AI agent workflows
  - Root CLAUDE.md exceeds ~150 lines or contains module-specific dev commands
  - AI agents apply rules from the wrong module (e.g., backend Alembic rules on frontend files)
tags: [claude-md, ai-agents, context-loading, module-scoping, single-source-of-truth, developer-experience]
related_components: [development_workflow, tooling]
---

# CLAUDE.md Files Should Be Scoped to Module Consumers, Not Human Readers

## Context

CLAUDE.md files written for human readers tend to grow into long, cross-module documents. A 500-line root CLAUDE.md containing backend Alembic migration rules, frontend emoji conventions, and agent PII redaction policies means an AI agent working only in `frontend/` loads all of that irrelevant context. This wastes context window, dilutes signal, and causes agents to apply rules from the wrong module.

The specific problems observed in this project:
1. Root CLAUDE.md was ~500 lines — agents working in a single module loaded irrelevant context from other modules
2. "Incremental formatting" rule appeared in root + all three module files (duplication)
3. Module CLAUDE.md files had inconsistent section orders and depths
4. Backend lacked a "Key Invariants" section; frontend's emoji rule wasn't prominently marked as an invariant

## Guidance

Apply a strict hierarchy with a content ownership table. Each piece of information lives in exactly one file.

**Root `CLAUDE.md`** (~120 lines max) contains only:
1. Behavioral guidelines (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution)
2. Project identity (one-paragraph overview + tech stack table)
3. Cross-cutting conventions (rules that apply to ALL modules: UI text in Chinese, error messages in Chinese, incremental formatting)
4. Module documentation table (pointers to module CLAUDE.md files)

**Module `CLAUDE.md`** files follow a standardized template:

```markdown
# {module}/CLAUDE.md

Module-specific guidance for {one-line description}.
See root `CLAUDE.md` for behavioral guidelines and cross-cutting conventions.

## Quality Commands
[bash block with all quality commands for this module]

## Tooling
- **{tool}:** description + config location

## Key Invariants
[Non-negotiable rules — things that must ALWAYS hold in this module]

## Don't Do
[Explicit anti-patterns — things AI agents should NEVER do here]

## Watch Out
[Gotchas, pitfalls, edge cases that commonly cause problems]

## Patterns
[Language/framework-specific patterns with examples]

## Links
- Root [`CLAUDE.md`](../CLAUDE.md)
- Module [`README.md`](./README.md)
```

**Content ownership table** — resolve every piece of content to exactly one file:

| Content | Lives in |
|---|---|
| Behavioral guidelines | Root only |
| "UI text in Chinese" | Root only |
| "Incremental formatting" rule | Root only (remove from module files) |
| Pydantic v2 patterns | `backend/CLAUDE.md` + `agent/CLAUDE.md` (acceptable duplication — independent modules) |
| Emoji convention | `frontend/CLAUDE.md` only |
| Risk control invariants (PII, policy guard) | `agent/CLAUDE.md` only |
| Alembic migration warning | `backend/CLAUDE.md` only |
| Dev commands | Each module's own file only |

Acceptable duplication: when two modules are truly independent (backend and agent both use Pydantic v2 but are deployed separately), duplicating the pattern in both files is better than a cross-module reference that requires loading both files.

## Why This Matters

AI agents load CLAUDE.md files as context at the start of each session. A 500-line root file means every agent — regardless of which module it's working in — pays the full context cost. More importantly, agents apply all loaded rules to their current task. Backend Alembic rules applied to a Vue component, or agent PII redaction rules applied to a backend router, produce incorrect behavior that's hard to debug.

The strict hierarchy ensures: an agent working in `frontend/` loads root CLAUDE.md (behavioral + cross-cutting) + `frontend/CLAUDE.md` (frontend-specific). It never sees backend or agent rules. Each module file is self-contained — the agent has everything it needs without reading other module files.

## When to Apply

- When adding a new module to the monorepo: create its CLAUDE.md from the template before writing any code
- When root CLAUDE.md exceeds ~150 lines: audit for module-specific content and move it
- When you notice an AI agent applying rules from the wrong module: check whether the rule is in the wrong file
- When the same rule appears in multiple files: pick one owner and remove the duplicates

## Examples

**Before** — root CLAUDE.md contains everything:
```markdown
# CLAUDE.md (500 lines)
## Backend
- Always run `alembic upgrade head` before starting...
- Pydantic v2 only — use ConfigDict...
## Frontend
- Emoji convention for toasts...
- No `as any` casts...
## Agent
- PII redaction before LLM calls...
- Policy guard on all requests...
## Dev Commands
cd backend && uv run pytest...
cd frontend && npm run typecheck...
```

**After** — root is thin, modules are self-contained:
```markdown
# CLAUDE.md (~120 lines)
## Behavioral Guidelines
[4 rules, unchanged]
## Cross-Cutting Conventions
- UI text in Chinese
- Error messages in Chinese
- Incremental formatting: format only files you touch
## Module Documentation
| Module | CLAUDE.md | README |
|--------|-----------|--------|
| Backend | backend/CLAUDE.md | backend/README.md |
| Frontend | frontend/CLAUDE.md | frontend/README.md |
| Agent | agent/CLAUDE.md | agent/README.md |
```

```markdown
# backend/CLAUDE.md (~150 lines)
## Quality Commands
[backend-only commands]
## Key Invariants
- Always run `alembic upgrade head` before starting on existing DB
- Pydantic v2 only
- Error messages in Chinese
## Patterns
[Pydantic v2 examples, import order, type annotations]
```

## Related

- CLAUDE.md restructuring spec: `docs/superpowers/specs/2026-04-23-claude-md-restructuring-design.md`
- Root [`CLAUDE.md`](../../CLAUDE.md) — the restructured version this doc describes
