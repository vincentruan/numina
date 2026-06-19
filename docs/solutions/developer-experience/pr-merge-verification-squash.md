---
title: "PR 合并状态验证：识别 squash merge 的陷阱"
date: "2026-06-19"
category: "developer-experience"
module: "git/GitHub PR 工作流"
problem_type: "developer_experience"
component: "development_workflow"
severity: "medium"
applies_when:
  - "清理已合并的 Git 分支前需要确认 PR 是否真的合入目标分支"
  - "通过 git 命令判断 PR 合并状态，发现 --is-ancestor 与 GitHub UI 不一致"
  - "批量清理分支脚本依赖 merge-base  ancestry 判断时"
tags:
  - "git"
  - "pr-merge"
  - "squash-merge"
  - "github-cli"
  - "branch-cleanup"
  - "gh-cli"
---

# PR 合并状态验证：识别 squash merge 的陷阱

## Context

用户发现两个分支（`fix/aihub-page-test` via PR #96、`refactor-chat-deerflow-parity` via PR #98）在 GitHub 上显示已合并，希望验证后清理分支。

用 `git merge-base --is-ancestor` 检查时：

- PR #96：返回 **YES**（ancestry 通过）
- PR #98：返回 **NO**（ancestry 失败）

于是得出"PR #98 未合并"的结论，保留了分支。直到用户坚持用 `gh pr view 98` 复核，才发现 PR #98 实际上**已经合并**，只是采用了 squash merge 方式，生成了新的 commit hash，原分支 commits 不在 main 的 ancestry 中。

## Guidance

**PR 合并状态验证的三种方法，按可靠性排序：**

### 方法 1：`gh pr view`（推荐，适用于所有合并方式）

```bash
gh pr view <N> --json state,mergeCommit,mergedAt
```

返回示例（squash merge）：

```json
{
  "mergeCommit": {"oid": "a97eb08cecf8..."},
  "mergedAt": "2026-06-17T11:44:28Z",
  "state": "MERGED"
}
```

这是最可靠的方式：无论 PR 是 merge commit、squash merge 还是 rebase merge，GitHub 都会准确记录合并状态和 merge commit。

### 方法 2：在 main 历史中 grep PR 编号（squash merge 的备用方案）

```bash
git log origin/main --oneline | grep "(#<N>)"
```

GitHub 默认在 squash merge commit 标题中附带 `(#<N>)`，例如：

```
a97eb08c refactor(backend,frontend): unify agent communication via AgentClient (#98)
```

即使 ancestry 不通，这条 grep 也能找到对应的 squash commit。

### 方法 3：`git merge-base --is-ancestor`（仅适用于常规 merge）

```bash
git merge-base --is-ancestor origin/<branch> origin/main && echo "merged" || echo "not merged"
```

**局限性**：只能检测 ancestry 关系。Squash merge 生成了全新 commit hash，原分支 commits 不在 main 历史中，ancestry 检查会返回 false —— 即使 PR 实际已合并。

**结论**：`--is-ancestor` 返回 true 是合并的充分证据；返回 false **不是**未合并的证据。

## Why This Matters

- **误判"未合并"的代价**：保留本应删除的分支，污染远程 refs；或在批量清理脚本中遗漏真正的已合并分支。
- **误判"已合并"的代价更严重**：如果反过来（ancestry 返回 true 但实际没合并），可能错误删除还未合入的分支，丢失未合并的代码。
- **Squash merge 是 GitHub 默认选项之一**：团队协作中很常见，不能假设所有 PR 都是常规 merge。
- **`--is-ancestor` 的"false negative"陷阱很隐蔽**：命令返回非 0 退出码看起来像"确定的否定"，实际上只是"无法证明"。

## When to Apply

- 在运行 `git push origin --delete <branch>` 或 `git branch -D` 之前
- 编写批量清理已合并分支的脚本时（不要用 `--is-ancestor` 作为唯一判断条件）
- 当 `git merge-base --is-ancestor` 返回 false，但 GitHub UI 显示 PR 已合并时
- 复核任何依赖 ancestry 的自动化判断时

## Examples

### 错误方式（本次踩坑）

```bash
# ❌ 仅凭 ancestry 判断，会漏判 squash merge
$ git merge-base --is-ancestor origin/refactor-chat-deerflow-parity origin/main
# 返回 1（false）
# 结论："PR 未合并" ← 错误！实际是 squash merge
```

### 正确方式（多层验证）

```bash
# ✅ 第一步：用 gh 权威查询
$ gh pr view 98 --json state,mergeCommit
{"mergeCommit":{"oid":"a97eb08c..."},"state":"MERGED"}

# ✅ 第二步：确认合并 commit 在 main 中
$ git log origin/main --oneline --grep="(#98)"
a97eb08c refactor(backend,frontend): unify agent communication via AgentClient (#98)

# ✅ 第三步：理解为什么 --is-ancestor 失败
# 分支 commit 0890ac36 被 squash 成 main 上的 a97eb08c
# 两个 hash 不同，ancestry 不通 —— 这是 squash merge 的正常行为，不是未合并
```

### 推荐的批量清理脚本判断逻辑

```bash
is_pr_merged() {
  local pr_num=$1
  local state
  state=$(gh pr view "$pr_num" --json state -q .state)
  [ "$state" = "MERGED" ]
}

# 用 gh pr list 获取所有 open PR 的编号，排除它们后再清理
# 而不是依赖 --is-ancestor 判断
```

## Related

- GitHub Docs: [About pull request merges](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges) — 三种合并方式的差异
- `git merge-base` man page — ancestry 检查的语义说明
- `gh pr view` 文档 — JSON 字段参考
