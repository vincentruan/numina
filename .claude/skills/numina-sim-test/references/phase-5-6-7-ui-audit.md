# Phase 5.6 — UI Quality Audit Details

> **Viewport:** Set browser to **375×812** (iPhone 13/14 baseline).
> Also test at **320×568** (iPhone SE 1st gen — smallest supported) and
> **768×1024** (tablet breakpoint) for UIQ.1. Record which width surfaced
> each issue.

Run [`test-cases/groups/g1-adult-stable/area15-ui-quality.md`](../test-cases/groups/g1-adult-stable/area15-ui-quality.md):

## Cases

- **UIQ.1** Mobile viewport baseline — no horizontal scroll at 320px/375px/768px, tab bars visible

- **UIQ.2** Dark mode (main app) — `van-config-provider` theme toggle, no inline-style leaks;
  verify WCAG AA contrast (≥4.5:1 normal text, ≥3:1 large text) on 5+ text elements per page
  (primary, secondary, amount, placeholder, disabled) via `getComputedStyle`
- **UIQ.3** Dark mode (child app) — CSS `[data-theme="dark"]` overrides, Clay palette check;
  same contrast verification as UIQ.2; also check transition flash (screenshot within 200ms of toggle)
- **UIQ.4** Vant4 component patterns — `:model-value` vs `:value`, popup teleport, three-state
  rendering (skeleton/empty/error/content); for error state: trigger validation on a required-field
  form (e.g., asset create), verify error messages appear adjacent to fields, readable in both modes,
  and use design tokens not inline colors
- **UIQ.5** Touch target sizing — ≥ 44×44px for all interactive elements
- **UIQ.6** Safe area compliance — `env(safe-area-inset-bottom)` for tab bars and fixed bottoms
- **UIQ.7** PWA offline behavior — offline banner, SW registration, install prompt
- **UIQ.8** Accessibility — enumerate **all** icon-only buttons per app (not spot-check 5);
  verify aria-labels on each; measure WCAG AA contrast ratios on key text/background pairs;
  test modal focus trap (open van-popup/showConfirmDialog, tab through, verify focus stays inside);
  verify `prefers-reduced-motion` emulation suppresses child celebration animations
- **UIQ.9** NProgress behavior — no flicker, no stuck spinner, visible when scrolled
- **UIQ.10** Cross-app style consistency — empty states, skeleton, toast, pull-refresh match between apps;
  use quantitative thresholds: skeleton within 300ms, EmptyState vertical center ±20px

> **Prerequisites:** Both adult (`$SID`) and child (`$SID_CHILD`) sessions active.
> Area 15 uses the adult session for UIQ.1–UIQ.9 and switches to child session
> for UIQ.3 + UIQ.10 child-side checks.
>
> **Design system reference:** [`references/ui-quality-checklist.md`](./ui-quality-checklist.md)
> contains full design token tables, dark mode methodology, and Vant4 patterns.

---

# Phase 5.7 — UX Review Agent Details

## Agent dispatch template

```
你是 Numina 仿真测试的 UI 体验审查员。基于本 Area 的截图
(dogfood-output/<case>.png, 用 Read 工具查看) 与 snapshot 记录, 逐 case 评估:

1. 功能输入输出: 断言是否真实满足 (不只看 pass 标记)
2. 交互连贯性: 点击→反馈→页面转换是否有断点 (按钮无反馈、加载态缺失、
   转场突兀、弹层遮挡输入焦点)
3. 视觉友好度: 元素错位/重叠、图标丢失或代字形 (□/□/私用区字符)、
   空间挤压 (文本截断/溢出)、对比度不足、移动端 375px 适配
4. 状态完整性: 骨架屏/空态/错误态是否合理呈现

输出格式 (每 case 一行 + 问题项展开):
- {case-id}: PASS|ISSUE — {一句体验结论}
ISSUE 项展开: {现象描述} / {影响面 (阻断/降级体验/轻微)} / {建议 (查什么)}

不要重新执行测试流程, 只做审查。不要修改任何文件。
```

## Orchestration rules

- **Timing:** After each Area group (G1/G2/G3) functional cases complete,
  dispatch immediately. Runs parallel with next group (review agent only
  reads screenshots, does not operate browser).
- **Input:** That Area's screenshots + per-case snapshot summary
  (failures / key interactions).
- **UI observation reuse:** Area 15 specific audit runs independently;
  Phase 5.7 supplements **all functional Areas**. Findings merge into
  report "UI 质量观察" section, tagged `UI-EXP`.
- **Smoke mode** can skip this phase; full/ai/travel/ui-quality must run it.
- **Failure taxonomy:** `UI-EXP` | 体验审查发现 | 输入输出正确但存在
  错位/图标丢失/不连贯等体验缺陷

> **Why a separate agent:** the main agent's context is full of assertions
> and driver commands → "I/O passes = pass" cognitive tunnel. An independent
> agent sees only screenshots and expectations, reviewing from a pure user
> perspective — consistent with "authoring vs review separation" principle.
