---
module: claude-code-tooling
date: 2026-05-16
problem_type: developer_experience
component: development_workflow
severity: medium
applies_when:
  - "Writing large files (specs, plans, markdown docs) using the Claude Code Write tool"
  - "Write tool call fails silently or returns a tool error on large content"
symptoms:
  - "Write tool fails silently with no output written to disk"
  - "Write tool returns InputValidationError: The required parameter file_path is missing / content is missing"
  - "Generated spec or plan file is empty or truncated after a Write call"
root_cause: missing_tooling
resolution_type: workflow_improvement
tags:
  - write-tool
  - heredoc
  - large-files
  - bash
  - file-writing
  - workaround
---

# Write Tool Large-File Failure — Bash Heredoc Workaround

## Context

When Claude Code agents attempt to write large files (spec documents, plan files, structured markdown) using the built-in Write tool, the tool can fail silently or throw misleading input validation errors:

```
InputValidationError: Write failed due to the following issues:
  The required parameter file_path is missing
  The required parameter content is missing
```

This was observed during a `/ce-plan` workflow generating a 400+ line structured markdown plan file. Multiple Write tool attempts failed consecutively. The error messages are misleading — the parameters are present, but the tool is rejecting the call for an undocumented size or content reason.

Two existing workflow docs (`workflow-issues/backend-module-extraction-workflow-2026-05-14.md`, `workflow-issues/server-monorepo-consolidation-phase2-2026-05-14.md`) each mention this symptom in a single bullet and suggest "minimize plan content" as a workaround. That workaround sacrifices document quality. This doc captures the correct solution.

## Guidance

For large file writes (roughly 200+ lines, or any file where Write tool failures have been observed), use a bash heredoc via the Bash tool instead of the Write tool.

```bash
cat > /absolute/path/to/file.md << 'PLANEOF'
# Your content here
...all lines...
PLANEOF
```

**Key rules:**
- Use a **quoted delimiter** (`'PLANEOF'` not `PLANEOF`) to prevent shell variable expansion inside the content — unquoted delimiters will expand `$variables` and break structured content.
- Always use an **absolute path**.
- After writing, do a **review pass**: check line count and scan the file to verify all required sections are present and nothing was truncated.

**Review step:**

```bash
wc -l /absolute/path/to/file.md   # confirm line count is reasonable
```

Then use the Read tool to scan the file and confirm all major sections from the source requirements are covered. If any section is missing, append it with another heredoc using `>>` instead of `>`.

## Why This Matters

The Write tool has undocumented size or content constraints that cause silent or misleading failures on large payloads. The bash heredoc bypasses the Write tool's validation layer entirely and delegates directly to the shell, which handles arbitrarily large content reliably.

Without this workaround, plan/spec generation workflows stall: the agent retries the Write tool repeatedly, fails each time, and either blocks or produces an empty file. The "minimize content" workaround from earlier docs sacrifices document completeness — the heredoc approach produces the full document without compromise.

## When to Apply

- Writing any markdown file expected to exceed ~150–200 lines.
- Writing spec, plan, design, or requirements documents generated from a structured template.
- Any time a Write tool call has already failed once on a given file, regardless of size.
- When the content contains special characters, nested code blocks, or structured YAML frontmatter that might interact poorly with the Write tool's input handling.

## Examples

**Before — Write tool failure:**

```
Write tool call → file_path=/path/to/plan.md, content=<400 lines>
→ InputValidationError: Write failed due to the following issues:
    The required parameter file_path is missing
    The required parameter content is missing
```

**After — bash heredoc success:**

```bash
cat > /Users/vincentruan/geek_space/github/numina/docs/plans/2026-05-16-multi-provider-model-selection-plan.md << 'PLANEOF'
---
name: multi-provider-model-selection
status: active
created: 2026-05-16
---

# 多供应商智能模型选择系统 — 实施计划

## 问题框架
...

## 实施单元
...
PLANEOF
echo "写入完成，行数: $(wc -l < /path/to/plan.md)"
# → 写入完成，行数: 438
```

**Review pass after writing:**

```bash
# 1. Confirm line count
wc -l /path/to/plan.md
# → 438

# 2. Confirm all major sections present
grep "^## " /path/to/plan.md
# → ## 问题框架
# → ## 关键决策与理由
# → ## 实施单元
# → ## 依赖与顺序
# → ## 风险与注意事项
# → ## 验证标准
```

If a section is missing, append it:

```bash
cat >> /path/to/plan.md << 'APPENDEOF'

## 验证标准

| 需求 | 验证方式 |
|------|---------|
| ...  | ...     |
APPENDEOF
```
