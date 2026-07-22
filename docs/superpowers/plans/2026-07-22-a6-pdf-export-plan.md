# A6 PDF 导出 — Implementation Plan

> **状态**：complete（A6 PDF 导出实现并验证，2026-07-22）
> **完成日期**：2026-07-22
> **日期**：2026-07-22
> **父文档**：[2026-07-22-p3-deferred-items-plan.md](./2026-07-22-p3-deferred-items-plan.md) §Deferred（A6 PDF）+ [2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md) §3 A6
> **范围**：A6 PDF 导出——client-side jsPDF，复用现有 reportImage.ts 的 html2canvas + getComputedStyle 捕获，多页拆分。**决策：client jsPDF**（非 server playwright）。
> **侦察依据**：A6 PDF scout（2026-07-22）。

---

## Product Decision（已确认 2026-07-22）

**A6 PDF = client jsPDF**。理由（侦察 grounded）：
- CSS var/主题难题已解决——`reportImage.ts` 的 `getComputedStyle` walk 直接复用，server 方案要从零复刻 ~400 行 Vue CSS + `[data-theme=dark]` 覆盖且永久同步维护
- server playwright 是 dev-only 依赖，backend Dockerfile `--no-dev` + 只装 tzdata——**容器无 chromium**，server 方案需 +300-400MB 镜像 + Dockerfile 改动，代价过大
- 报告 indicator 卡 schema 限定 3-8 个（`ai_result_parser.py:60`），长度中等，多页拆分可控
- 代价：光栅 PDF（文字不可选），但"报告归档"用途视觉保真度足够（与现有 PNG 导出同 fidelity）

---

## Goal Capsule

**一句话**：AIReportPage 加"导出 PDF"按钮，复用 reportImage.ts 的 html2canvas+getComputedStyle 捕获 canvas，用 jsPDF 多页拆分（A4）生成 PDF 下载。

**为什么**：A6 图片导出已完成，PDF 补齐报告归档能力。client jsPDF 复用已有捕获逻辑（CSS var/主题已解决），无后端改动、无容器膨胀。

**完成标准**：导出 PDF 按钮 + jsPDF 多页拆分 + i18n；`pnpm typecheck` + `pnpm test:run` 不新增失败。

---

## Planning Contract

### 侦察结论
- `utils/reportImage.ts`：`generateReportImage(reportEl)` 已克隆 DOM + `inlineComputedStyles` walk（~25 CSS 属性，解决 var()/oklch）+ `html2canvas({scale:2})` → canvas。**jsPDF 复用同一 canvas**（`addImage` 而非 `toBlob`）。
- `AIReportPage.vue:54` `<div ref="reportContentRef">` 包裹全报告（score ring + indicators + regen）；`onExportImage:377` 已有图片导出按钮 + `isExportingImage` 状态。
- indicator 卡 schema 3-8 个（`ai_result_parser.py:60`），narrative/suggestions 是 LLM markdown 变长。
- html2canvas 已是依赖（`package.json`）；**需加 `jspdf`**。

### KTD-1：复用 reportImage 捕获，jsPDF 消费 canvas
- 扩展 `reportImage.ts`（或新 `reportPdf.ts`）：`generateReportPdf(reportEl): Promise<Blob>`。
- 复用 `inlineComputedStyles` + 克隆 + html2canvas 拿到 canvas（与 `generateReportImage` 共享核心逻辑，抽公共 `captureReportCanvas(reportEl)` helper）。
- jsPDF：`const pdf = new jsPDF({orientation:'portrait',unit:'pt',format:'a4'})`；A4 pt = 595×842。canvas 按 A4 宽度缩放，高度按比例切多页（`addImage` + `addPage`，y 偏移负值切片或 canvas 切片）。
- **多页拆分策略**：canvas 总高 / A4 内容高 = 页数；逐页 `pdf.addImage(canvas, 'PNG', 0, -offsetY, a4Width, canvasHeight)` + `addPage`。注意避免卡片文字被切断（可接受简单切，或按 indicator 卡边界分页——决策：**简单等高切**，MVP 不做卡边界对齐，留后续）。

### KTD-2：AIReportPage 加导出 PDF 按钮
- 在现有导出图片按钮旁加"导出 PDF"按钮（`van-button`，loading 绑 `isExportingPdf`）。
- `onExportPdf`：`showLoadingToast` → `generateReportPdf` → `downloadBlob(blob, 'numina-report-{date}.pdf')` → 成功 toast；失败 `showFailToast`。
- 复用 `reportImageFilename` 风格的日期命名。

### KTD-3：依赖 + i18n
- `package.json` 加 `jspdf`（`pnpm add jspdf` in frontend/apps/main）。
- i18n：`aiReport.exportPdf` = "导出 PDF"/"Export PDF"，`aiReport.exportingPdf` = "正在生成 PDF..."/"Generating PDF..."，`aiReport.exportPdfSuccess`/`exportPdfFail`。

### Sequencing
1. 加 jspdf 依赖。
2. `reportImage.ts` 抽 `captureReportCanvas` + 加 `generateReportPdf`（多页拆分）。
3. AIReportPage 加按钮 + handler。
4. i18n 双 locale。

---

## Implementation Units

| ID | 任务 | 改动点 | Effort |
|----|------|--------|--------|
| A6-a | jspdf 依赖 + reportImage 抽 captureReportCanvas + generateReportPdf 多页 | package.json + utils/reportImage.ts | small-medium |
| A6-b | AIReportPage 导出 PDF 按钮 + handler | AIReportPage.vue | small |
| A6-c | i18n 双 locale | zh-CN.ts + en-US.ts | trivial |

---

## Verification Contract

- `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ；`pnpm lint` touched 0 新增。
- 手动：导出 PDF → 多页、含 score ring + indicator 卡、主题颜色正确、CJK 文字渲染（html2canvas 已渲染，jsPDF 图片贴入无字体问题）。
- 无 fake completion。

---

## Definition of Done

- [x] A6-a：jspdf 依赖（v4.2.1）+ `captureReportCanvas` 抽取（image+PDF 共享 CSS-var 解析）+ `generateReportPdf`（A4 多页拆分，负 y 偏移切片）。
- [x] A6-b：AIReportPage 导出 PDF 按钮 + onExportPdf handler（loading/success/fail toast）+ downloadBlob helper。
- [x] A6-c：i18n 双 locale（exportPdf/exportingPdf/exportPdfSuccess/exportPdfFail）。
- [x] `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ suite；`pnpm lint` touched 0 新增（3 预存 warning）；现有图片导出 `generateReportImage` 不破坏。
- [x] 无 fake completion。
