---
title: Family Manifesto - 家庭约定签署功能 - Plan
type: feat
date: 2026-07-30
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Family Manifesto - 家庭约定签署功能

## Goal Capsule

- **Objective:** 让家庭在 Numina 中创建、签署并展示一份「家庭约定/宣言」，使 Owner 感到掌控、Member 感到参与、Child 感到被纳入家庭故事并获得参与感与得到感。V1 包含完整的 Child 端约定意义感功能、Member 反馈渠道、以及 PDF 模板签署体系。
- **Authority:** 产品决策来自 `docs/family-manifesto-design.md` 的四条设计原则（P1-P4）和三角色画像；本文解决交互连贯性缺口和八个开放问题（Q1-Q5 + O1-O3）。
- **Open blockers:** 无。所有产品决策已确认。

---

## Product Contract

### Problem Frame

Numina 已有丰富的角色感知体系（Owner 管理、Member 参与、Child 完成），但缺少一个**全家共同可见、共同承诺的仪式性载体**。现有的家庭设置是 Owner 单方面配置的；成员和 child 只看到结果，没有参与决策的感觉。

「家庭约定」填补这个空白：一份由 Owner 发起、全员签署的家庭宣言。它不是合同，是一个「我们全家都同意这样做」的可视化承诺。

### Requirements

**R1. PDF 模板体系 + 有限编辑**

约定采用固定视觉样式的 PDF 模板，呈现为正式的契约/证书风格，支持多人署名布局。

**模板管理：**
- 系统预置多份 PDF 模板，每份模板有中文和英文两个语言版本
- 系统根据家庭管理员的语言偏好自动排序（匹配语言排前面），但 Owner 可手动选择任一模板
- 模板样式固定（字体、排版、签名区域布局不可自定义），Owner 仅可编辑：标题 + 正文内容

**编辑约束：**
- 标题：单行文本，限制长度
- 正文：富文本区域，支持基本格式（段落、换行）
- 签名区域：由系统自动根据家庭成员生成，不可编辑

**模板选择体验：**
- 创建时先展示模板预览列表（缩略图 + 名称），选中后进入编辑
- 编辑过程中可随时切换模板（内容保留，样式替换）
- 预览页显示最终效果（含所有家庭成员的签名占位）

**R2. 可选签署截止时间**

Owner 创建约定时可设定签署截止时间，也可不设。截止时间到期后未全员签署的约定状态为「等待签署」，不标红不警告。Owner 可延长截止时间或直接标记为「已生效」。

**R3. 签署后不可撤回**

签署是严肃的承诺，一旦签署不可撤回。如需修改约定内容，由 Owner 修改并重新发布新版本，全员重新签署。此设计与 P4「暂停即尊重」的衔接：通过 Owner 修改约定的「小幅修改」标记（见 R4）和冷静期弹窗来体现，而非通过撤回机制。

**R4. 版本管理与小幅修改标记**

每次约定被修改并重新发布时，自动保存快照（时间戳 + 修改人 + 内容）。V1 不做版本对比 UI。历史快照仅 Owner 可查看。

Owner 发布新版本时选择修改类型：
- **小幅修改**（错别字、措辞优化）：声明修改不影响核心承诺，只更新快照，**不触发**全员重新签署流程。已签署状态保持不变。
- **重大修改**（新增/删除条款、改变核心承诺）：**触发**全员重新签署。已签署的成员收到强制弹屏，未签署的成员同步收到弹屏。

条款变更时在约定页顶部显示「约定已更新」提示（小幅修改也显示，但标注为「措辞优化」）。

**R5. 被动同步，与现有架构一致**

约定数据存服务端（family 级别）。打开 app 时被动检查最新状态，与 V1 Manifesto 的 `van-notify` 被动检查模型一致。签署动作即时同步到当前设备，其他设备在下次页面加载时更新。不做 WebSocket 实时推送。

**R6. Owner 创建与发布流程**

入口在家庭设置页。创建流程：选择 PDF 模板（预览缩略图列表，按 Owner 语言排序）→ 编辑标题 + 正文 → 预览（显示最终 PDF 效果 + 所有成员的签名占位）→ 设定可选截止时间 → 发布。发布后全员收到强制弹屏。

正文中 Owner 可选择性地将条款标记为「可追踪」（与 Child 任务系统软关联，见 R11）。

重新发布流程（修改已有约定）：编辑标题/正文 → 选择修改类型（小幅修改 / 重大修改）→ 发布。小幅修改只更新快照不触发重新签署；重大修改触发全员重新签署弹屏。

**R7. Member 签署流程**

登录后根组件被动检查（`onMounted` / `onActivated`）是否有新版本未签署。若有，弹出通知弹窗（`<Teleport to="body">` overlay），提示「家庭约定已更新，请签署」，点击后跳转到专用签署页 `/manifesto/sign`。

**签署页 (`ManifestoSignPage.vue`)：**
- 使用 `ManifestoViewer` 展示完整约定内容
- 滚动到底部后启用签名区域（`IntersectionObserver` + 3 秒定时器双门控）
- 签名区域展示 `SignaturePad`，完成后「确认签署」按钮可用
- 签署后调用 API → 返回首页 → 刷新 Dashboard

**反馈渠道（V1 纳入）：**
- 约定详情页底部有「我有想法」按钮，点击展开文本输入框
- 反馈提交后 Owner 在设置页约定管理区看到未读反馈提示（小红点 + 数字）
- 反馈不阻断签署流程，签署后可以随时提交
- 反馈对 Owner 可见，其他 Member 不可见（避免从众效应）

**R8. Child 签署流程**

Child app 登录后根组件同样被动检查（`onMounted` / `onActivated`）是否有新版本未签署。若有，弹出 Clay 风格通知弹窗提示「家庭约定等你签署哦」，点击后跳转到专用签署页 `/manifesto/sign`。

签署页以 Clay 品牌风格展示约定（简单语言、大字体、品牌色）。签署体验有仪式感：签名/盖章动画 + celebration（与 U2 celebration 复用）。签署后约定以一行摘要形式出现在 Child 首页（"我们家的约定：XX"）。

年龄分支签署方式：
- **< 5 岁**：双选项（① 点击"同意"按钮 + 二次确认弹窗，`signature_data` 存 NULL ② 手写签名），低龄儿童可选择简单方式。Viewer 组件检测 `signature_data IS NULL` 时渲染 "✓ 已同意" glyph
- **≥ 5 岁或年龄未知**：强制手写签名，确保签署的严肃性

未签署的 Child 每次打开 app 都会看到弹窗提示，但不产生催促焦虑感。

**R9. 约定展示位置**

签署完成后约定不能只埋在设置页：
- **Main app Dashboard:** 可折叠卡片「家庭约定」，显示约定标题 + 签署状态（X/Y 已签署）
- **Main app 设置页:** 完整的约定管理入口（编辑/重新发布/查看历史快照）
- **Child app 首页:** 一行摘要 + 签署状态，点击进入完整约定页

**R10. 约定与现有设计原则的对齐**

- P1 掌控不焦虑：Owner 发布前有「影响预览」，破坏性操作（删除/修改已签署约定）使用 BottomSheetConfirm
- P2 参与不旁观：Member 有反馈渠道（「我有想法」），Dashboard 卡片平等展示
- P3 成就不压力：未签署状态不产生焦虑感，用「等你回来」语气而非「已超时」
- P4 暂停即尊重：签署是不可撤回的严肃承诺，但 Owner 修改已签署约定时通过「小幅修改」标记避免不必要的重新签署，重大修改时全员重新签署前有冷静期确认

**R11. Child 签署后意义感（V1 完整功能）**

约定签署后不能只是静态展示——要让 Child 感到参与感和得到感，觉得「这份约定跟我有关、对我有意义」。

**签署仪式强化：**
- 签署完成后立即触发 celebration 动画 + 专属成就徽章（"家庭约定守护者"）
- 签署瞬间有音效/触感反馈，强化仪式感

**首页动态摘要：**
- 签署后 Child 首页摘要不是静态文字，而是动态的参与式展示
- 显示所有签署者的头像/昵称（"爸爸、妈妈、小宝 共同约定"），不只是文字
- 摘要文案用引导性语气："我们全家一起约定的：XX"，暗示共同承诺

**约定与日常连接的钩子：**
- 约定正文中如有与任务相关的条款（如"每天阅读 30 分钟"），V1 支持 Owner 在发布时将条款标记为「可追踪」
- 被标记的条款在 Child 任务列表中显示关联提示："这个任务和我们的家庭约定有关哦"
- 不做自动联动（不改变任务逻辑），只做视觉关联提示

**签署纪念感：**
- 约定详情页显示「签署纪念日」：全家人在这一天共同签署了约定
- 满一个月/一年时显示温和庆祝提示："我们的约定已经陪伴我们 30 天了"

### Scope Boundaries

**V1 范围：**
- 约定的 CRUD（Owner）
- 签署流程（所有角色，不可撤回）
- PDF 模板体系（多语言、固定样式、有限编辑）
- 强制弹屏签署机制
- Dashboard 展示卡片
- Child 端签署体验 + 签署后意义感功能（R11）
- Member 反馈渠道（「我有想法」）
- 版本快照 + 小幅修改标记（Owner 可查看）
- 条款「可追踪」标记（Child 任务列表软关联提示）

**V1 不做：**
- 约定的自动翻译（Owner 自己写简单版本给 Child）
- 版本对比 UI（手动查看快照内容）
- WebSocket 实时推送（沿用被动检查）
- 约定的定时提醒 / 推送通知
- 跨家庭的约定分享
- 条款的自动任务联动（V1 只做视觉提示，不改变任务逻辑）

### Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| Q1: 预置模板 | PDF 模板体系，多语言版本，Owner 仅编辑标题+正文 | 契约/证书风格强化仪式感；固定样式保证视觉质量；有限编辑降低 Owner 设计负担 |
| Q2: 签署截止时间 | 可选；逾期不惩罚，状态为「等待签署」 | 约定不是考试，逾期 ≠ 失败；符合 P3 |
| Q3: 签署后撤回 | 不允许撤回 | 签署是严肃承诺；修改通过 Owner 发布新版本实现；符合不可撤回的审计需求 |
| Q4: 历史版本 | V1 快照 + 小幅修改标记 | 小幅修改不触发重新签署，重大修改触发全员重签 |
| Q5: 多设备同步 | 被动检查，与 `van-notify` 模型一致 | 沿用现有架构，零额外基础设施成本 |
| O1: Child 意义感 | V1 完整功能 | 签署后意义感是 Child 长期使用的核心动力；成就徽章+动态摘要+条款追踪提示+签署纪念日 |
| O2: Member 反馈 | V1 纳入「我有想法」按钮 | 低成本高价值，填补签署后参与感断裂；反馈仅 Owner 可见 |
| O3: 条款结构化 | 自由文本，模板内可拖拽排序 | PDF 模板已提供隐性结构；拖拽排序保持灵活可读性 |
| V1 功能定位 | 展示/仪式感 + Child 意义感，不做自动任务联动 | 降低联动复杂度，视觉提示足够传递关联感 |
| Child 语言 | Owner 自己写简单版本，不自动翻译 | V1 范围控制，避免引入 NLP 依赖 |
| 展示位置 | Dashboard 卡片 + 设置页管理入口 + Child 首页动态摘要 | 约定需要日常可见，不能埋在设置页 |

### P1 Detail Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| P1-1: 年龄未知签署分支 | 手写签名分支（对齐 R8） | 年龄未知时倾向严肃性，≥5 或未知均要求手写 |
| P1-2: 强制签署机制 | 弹窗提示 + 跳转签署页 | 弹窗作为通知层（非阻断式），点击后跳转到专用签署页面完成阅读+签署。Member 和 Child 均用此模式 |
| P1-5: 低龄儿童"同意"数据形态 | 可空 signature_data + Viewer 渲染 "✓ 已同意" | 不引入额外 `signing_method` 列；Viewer 组件检测 `signature_data IS NULL` 时渲染 "✓ 已同意" glyph |
| P1-6: 正文编辑器 | 轻量块编辑器（每块=一段落） | 替代 textarea + 空行分割方案。每段独立卡片，可单独标记「可追踪」，所见即所得 |
| P1-7: 小幅修改签名持久化 | 向前复制签名 | Owner 发布小幅修改时，service 层将旧版本所有签名复制到新版本。保证 R3"签署不可撤回"和 R4"小幅修改不触发重签"的一致性 |

### Open Questions

- ~~**O1: Child 签署后意义感的深度。**~~ ✅ 已纳入 R11：V1 完整功能——成就徽章、动态摘要、条款「可追踪」标记、签署纪念日。
- ~~**O2: Member「我有想法」反馈按钮。**~~ ✅ 已纳入 R7：反馈文本输入 + Owner 端未读提示，仅 Owner 可见。
- ~~**O3: 约定条款的结构化程度。**~~ ✅ 已确认：自由文本 + 拖拽排序，PDF 模板提供隐性结构。
- ~~**O4: Owner 修改已签署约定的流程。**~~ ✅ 已纳入 R4：小幅修改标记机制。Owner 声明修改不影响核心承诺时，只更新快照不触发重新签署。

**所有开放问题已解决。文档可进入 implementation-ready 阶段。**

### Sources

- `docs/family-manifesto-design.md` — 角色画像 + P1-P4 原则
- `docs/design/family-interaction-rules.md` — 交互规范（动画时长、弹窗分类）
- `docs/plans/2026-07-30-001-feat-family-manifesto-v1-role-aware-ux-plan.md` — V1 UX 实现计划（celebration, swipe, shimmer 等）

### 交互连贯性审查备注

审查原始需求文档时发现以下连贯性缺口，已在本 plan 中通过 R3-R8 的设计解决：

| 缺口 | 原始需求的问题 | 本 plan 的解决方式 |
|------|---------------|-------------------|
| 草稿持久性 | F1.1 说"保存为草稿"但未定义刷新/退出后草稿是否保留 | R6 隐含：草稿为 session 级，退出 app 前需提示"是否保存草稿" |
| "重新发布"语义 | F2.1 有"重新发布"按钮但未定义与"发布"的区别 | R6 明确：重新发布 = 修改已有约定，需选择修改类型（小幅/重大） |
| 弹屏重复触发 | F3.1 未说明关闭弹屏后是否反复弹 | R7/R8 明确：每次打开 app 有新版本未签署时都弹，直至签署完成 |
| 签署后可查看性 | F2.1 只显示"签署状态"，成员看不到签署详情 | R7 补充：Dashboard 卡片显示签署时间 + 签署方式 |
| 年龄来源 | F3.3 依赖"用户年龄"但未定义字段来源 | 实现时需确认：从用户 profile 的 birthday 字段计算；年龄未知走 ≥5 分支 |
| Child app 弹屏 | 需求未说明 Child app 是否也有弹屏 | R8 明确：Child app 同样触发弹屏提示（P1-2：弹窗通知 + 跳转签署页） |

**Product Contract preservation:** unchanged — all R-IDs, Key Decisions, and Scope Boundaries carried as-is from `ce-brainstorm`.

---

## Planning Contract

### Key Technical Decisions

KTD1. **Frontend Vue component templates instead of server-rendered PDFs or binary template storage.** The "PDF 模板体系" (R1) describes a visual style — formal certificate/contract layouts — not a requirement for downloadable PDF output. Templates are Vue SFCs with fixed CSS layouts that accept `title`, `body` props and render signature slots from family member data. Template catalog is hardcoded in a `templateRegistry.ts` (V1 ships 2 templates × 2 languages = 4 template entries). Adding new templates requires a code change — acceptable for V1. This avoids binary storage infrastructure, jspdf client-side rendering for every view, and file-serving complexity. `html2canvas` + `jspdf` (already in main app) are available for future PDF export but not used for display. Governs R1.

KTD2. **Canvas-based signature pad with touch + mouse events, no external library.** The signature pad is used in both Member forced-signing popup and Child signing ceremony. Building a custom `<SignaturePad>` component using native `<canvas>` with `pointerdown`/`pointermove`/`pointerup` events (unified touch+mouse API) keeps the bundle small (~0 KB added) and avoids a new dependency for one feature. The component exposes `clear()`, `isEmpty()`, `toDataURL()` methods. Min stroke width 1.5px, max 3px (pressure-like effect via velocity). Canvas resolution: `devicePixelRatio`-aware to prevent blur on Retina displays. Governs R7, R8.

KTD3. **Signature stored as base64 PNG data URL, nullable for child tap-to-consent (P1-5).** The signed canvas is converted to a compressed PNG data URL via `canvas.toDataURL('image/png', 0.5)` (50% quality). Stored in `manifesto_signatures.signature_data` as TEXT (nullable). For child age < 5 who taps "同意", `signature_data` is stored as NULL — no 1x1 PNG placeholder. The `ManifestoViewer` component checks `signature_data IS NULL` and renders a "✓ 已同意" glyph instead of a signature image. Client-side size limit of 50KB enforced for non-null signatures (re-compress if exceeded). This avoids file upload infrastructure and the existing `StorageBackend` abstraction, keeping signature data co-located with the signing record. Storage estimate: ~2-10KB per signature × ~5 family members × ~10 versions = ~500KB total per family — negligible. Governs R3, R7, R8.

KTD4. **Forced signing: popup notification + dedicated signing page (P1-2).** Root-level component (in `App.vue` or a layout wrapper) checks for unsigned manifesto on `onMounted` / `onActivated`. When unsigned exists: show a non-blocking notification popup (`<Teleport to="body">`, `z-index: 1000`, `role="dialog" aria-modal="true"`) with manifesto title and a CTA button. Clicking the CTA navigates to `/manifesto/sign` (Member) or `/child/manifesto/sign` (Child). The signing page handles the actual reading + signing flow. For Member signing page: scroll-to-bottom (`IntersectionObserver` on last content element) + 3-second timer gate before enabling the signature pad. Both conditions must be true. 5-second safety timeout prevents stuck overlays (per nprogress learning). For Child signing page: simplified with Clay tokens, larger fonts (≥18px body), age-branched signing (P1-1: unknown age → handwriting branch). Governs R7, R8, R10.

KTD5. **Trackable clauses: block editor with per-block toggle (P1-6).** Instead of a single textarea with blank-line splitting, the body editor uses a lightweight block editor — each block represents one paragraph. The `<BlockEditor>` component renders an ordered list of paragraph blocks, each with its own `van-switch` to mark as "trackable". Adding/removing/reordering blocks is done via drag handles or +/− buttons. The component outputs `{ body: string, trackable_clause_indices: number[] }` — the body is the concatenated text (blocks joined by `\n\n`), and the indices map to 0-based paragraph positions. Stored as JSON array `[0, 2, 5]` in `ManifestoVersion.trackable_clause_indices`. On child task page, if trackable clauses exist, show an inline hint: "这个任务和我们的家庭约定有关哦". No automatic task-clause linking — purely visual. Governs R6, R11.

KTD6. **Split API: `/api/v1/family/manifesto` (main app) + `/api/v1/child/manifesto` (child app).** Main app router (prefix `/family`) handles full CRUD + sign + feedback + history — requires `require_adult` (Owner or Member). Child app router (prefix `/child`) handles read + sign only — requires `get_current_child_user` (the codebase's child auth dependency, at `auth/deps.py:371`; there is no `require_child` function). Both routers share the same service layer but have separate request/response schemas to enforce role-specific access. Family_id derived from JWT `user.family_id`, never from request body. `ManifestoSignRequest.signature_data` must have `max_length=70000` (~50KB base64) for server-side size validation. Governs R5, R6, R7, R8.

KTD7. **Service layer uses session-as-argument pattern.** `ManifestoService` accepts `db: Session` as parameter (not `SessionLocal()`). Follows the audit-service learning: session-as-argument prevents test isolation failures. All CRUD operations go through the service; routers are thin HTTP adapters. Governs R5.

KTD8. **Celebration integration for child signing via `useCelebration` extension.** When child signs manifesto, the signing API returns a success response. The child app triggers `CelebrationAnimation` with a new `'manifesto-signed'` context. Reuses existing `<Teleport to="body">` + `z-index: 999` pattern. The "家庭约定守护者" badge is awarded via the existing milestone/achievement system (new milestone type `manifesto_signed`). Governs R8, R11.

KTD9. **Dashboard card: self-contained SFC with own data fetch + `van-collapse`.** Follows existing dashboard card pattern (e.g., `SmartRemindersCard.vue`, `LiteracyStatusCard.vue`). `ManifestoDashboardCard.vue` fetches signing status from `GET /family/manifesto/dashboard-summary` on mount. Uses `van-collapse` for expand/collapse. Self-gates visibility: `visible = false` when no active manifesto exists. Governs R9.

KTD10. **Template language sorting: owner language preference first, then other language.** Templates in the registry carry a `lang` field (`'zh'` | `'en'`). On template selection, sort by owner's language preference (from `user.locale` or family language setting) — matching language first. Owner can still select any template regardless of language. Governs R1, R6.

KTD11. **Minor update copies signatures forward (P1-7).** When Owner publishes a minor update (`change_type='minor'`), `ManifestoService.publish_update()` creates the new version AND copies all signatures from the previous version to the new version. This preserves the "签署不可撤回" (R3) contract: members who already signed remain signed across minor revisions. For major updates (`change_type='major'`), no signatures are copied — everyone must re-sign. The `ALREADY_SIGNED` (409) check must account for copied signatures: if a signature record already exists for the current user on the new version (because it was copied), the user has already "signed" and `get_unsigned_check` should not return this manifesto for them. Governs R3, R4.

### Assumptions

- The `User` model has a `locale` or language preference field (or falls back to family-level language setting) for template sorting. If not, use the main app's current locale (`useI18n().locale`).
- The family member list API (`GET /family/members`) returns all members including children, with their names and roles — needed for signature slot generation.
- The child app's `require_child` auth dependency exists and works analogously to `require_adult`.
- `html2canvas` and `jspdf` remain available in the main app for potential future PDF export (not used in V1).
- The existing `useCelebration` composable can be extended with a new trigger type without breaking the task-completion celebration flow.
- Family member count is small (2-6 members), so per-member signature data volume is negligible.
- Template images (thumbnails) can be inline SVG or simple CSS previews — no external image assets needed.

---

## Implementation Units

### U1. Backend Data Models + Alembic Migration

**Goal:** Create SQLAlchemy models for the manifesto domain and an Alembic migration to add the tables.

**Requirements:** R1, R2, R3, R4, R5, R7, R8, R11

**Dependencies:** None (foundational)

**Files:**
- `server/apps/backend/app/models/manifesto.py` (new)
- `server/apps/backend/app/models/__init__.py` (modify — export new models)
- `server/apps/backend/alembic/versions/XXXX_manifesto_tables.py` (new — autogenerated)
- `tests/backend/models/test_manifesto_models.py` (new)

**Approach:**
1. Create `FamilyManifesto` model: `id` (snowflake), `family_id` (BigInteger, indexed), `current_version_id` (BigInteger, nullable, FK to `manifesto_versions.id`), `status` (String(20): `'draft'` / `'active'` / `'archived'`), `signing_deadline` (DateTime, nullable), `created_by` (BigInteger), `created_at`, `updated_at`.
2. Create `ManifestoVersion` model: `id` (snowflake), `manifesto_id` (BigInteger, FK), `version_number` (Integer), `template_id` (String(50)), `title` (String(200)), `body` (Text), `change_type` (String(20): `'initial'` / `'minor'` / `'major'`, default `'initial'`), `trackable_clause_indices` (JSON, nullable), `signed_at` (DateTime, nullable — last full-sign timestamp), `created_by` (BigInteger), `created_at`.
3. Create `ManifestoSignature` model: `id` (snowflake), `version_id` (BigInteger, FK), `user_id` (BigInteger), `signature_data` (Text, **nullable** — NULL for child age < 5 tap-to-consent, base64 PNG data URL otherwise), `signed_at` (DateTime).
4. Create `ManifestoFeedback` model: `id` (snowflake), `manifesto_id` (BigInteger, FK), `user_id` (BigInteger), `content` (Text), `is_read` (Boolean, default False), `created_at`.
5. All models have `family_id` column (indexed) for family-scoped queries.
6. Generate Alembic migration via `alembic revision --autogenerate -m "add_manifesto_tables"`.
7. Import new models in `alembic/env.py` so autogenerate detects them.

**Patterns to follow:** `FamilySetting` model for family-scoped column pattern; `FamilyDebtThresholds` for FK pattern; existing migration naming convention (`XXXX_description.py`).

**Test scenarios:**
- All four tables created with correct column types and constraints
- `family_id` column is indexed on all tables
- FK relationships resolve correctly (version → manifesto, signature → version, feedback → manifesto)
- Snowflake ID generation works for all models
- Alembic `upgrade head` + `downgrade -1` round-trips cleanly

**Verification:** `alembic upgrade head` succeeds; models importable; backend tests pass.

---

### U2. Backend API Endpoints + Schemas + Service

**Goal:** Implement the manifesto API layer — schemas, service, and two routers (main app + child app).

**Requirements:** R1-R11

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/schemas/manifesto.py` (new)
- `server/apps/backend/app/services/manifesto_service.py` (new)
- `server/apps/backend/app/routers/manifesto.py` (new)
- `server/apps/backend/app/routers/child_manifesto.py` (new)
- `server/apps/backend/app/main.py` (modify — register new routers)
- `server/apps/backend/app/errors/codes.py` (modify — add manifesto error codes)
- `server/apps/backend/app/errors/locales/zh-CN.json` (modify — add manifesto error messages)
- `server/apps/backend/app/errors/locales/en-US.json` (modify — add manifesto error messages)
- `tests/backend/api/test_manifesto_api.py` (new)
- `tests/backend/api/test_child_manifesto_api.py` (new)

**Approach:**
1. Define Pydantic schemas in `schemas/manifesto.py`:
   - Request: `ManifestoCreateRequest` (template_id, title, body, signing_deadline?, trackable_clause_indices?), `ManifestoPublishRequest` (title?, body?, change_type, trackable_clause_indices?), `ManifestoSignRequest` (signature_data: **Optional[str]** — nullable for child tap-to-consent), `ManifestoFeedbackCreateRequest` (content)
   - Response (all inherit `SnowflakeBase`): `ManifestoResponse`, `ManifestoVersionResponse`, `ManifestoSignatureResponse`, `ManifestoDashboardSummaryResponse`, `ManifestoFeedbackResponse`, `ChildManifestoResponse`, `ChildTrackableClausesResponse`, `UnsignedManifestoCheckResponse`
2. Implement `ManifestoService` with session-as-argument pattern:
   - `create_manifesto(db, family_id, user_id, req)` — creates manifesto + initial version, sets status='active'
   - `get_current_manifesto(db, family_id)` — returns manifesto with latest version + signatures
   - `publish_update(db, manifesto_id, user_id, req)` — creates new version with change_type; **if `change_type='minor'`, copies all signatures from previous version to new version (P1-7)**
   - `sign_manifesto(db, version_id, user_id, req)` — creates signature record; `signature_data` may be None (child tap-to-consent, P1-5)
   - `get_unsigned_manifesto(db, family_id, user_id)` — returns active manifesto if user hasn't signed latest version
   - `get_version_history(db, manifesto_id)` — returns all versions (owner-only)
   - `submit_feedback(db, manifesto_id, user_id, req)` — creates feedback record
   - `get_dashboard_summary(db, family_id)` — returns title + signed/total counts
   - `get_child_manifesto(db, family_id, user_id)` — returns manifesto + child's signing status
   - `get_trackable_clauses(db, family_id)` — returns trackable clause indices from latest version
3. Main app router (`/family/manifesto` prefix):
   - `POST ""` → create (owner only, `require_owner`)
   - `GET ""` → get current (adult)
   - `GET "/unsigned-check"` → unsigned check (adult)
   - `PATCH ""` → publish update (owner only)
   - `POST "/sign"` → sign (adult)
   - `GET "/history"` → version history (owner only)
   - `POST "/feedback"` → submit feedback (adult)
   - `GET "/feedback"` → list feedback (owner only)
   - `GET "/dashboard-summary"` → dashboard summary (adult)
4. Child app router (`/child/manifesto` prefix):
   - `GET ""` → get manifesto for child (child only, `require_child`)
   - `POST "/sign"` → sign (child only)
   - `GET "/trackable-clauses"` → trackable clause indices (child only)
5. Register both routers in `main.py`.
6. Add error codes: `MANIFESTO_NOT_FOUND`, `MANIFESTO_ALREADY_SIGNED`, `MANIFESTO_NOT_ACTIVE`.

**Patterns to follow:** `family.py` router for `require_owner` / `require_adult` patterns; `schemas/base.py` for `SnowflakeBase`; `config_service.py` for session-as-argument service pattern; `AppError` + `ErrorCode` for error handling.

**Test scenarios:**
- Owner creates manifesto → 201, status='active', version 1 created
- Non-owner cannot create manifesto → 403
- Member signs manifesto → signature record created with non-null signature_data
- Member cannot sign same version twice → 409 (ALREADY_SIGNED)
- Owner publishes minor update → new version created, **all signatures copied from previous version** (P1-7); `get_unsigned_check` for already-signed members returns empty
- Owner publishes major update → new version created, **no signatures copied**, all members must re-sign
- Child signs via tap-to-consent → signature record created with `signature_data=NULL` (P1-5)
- Child signs via handwriting → signature record created with non-null signature_data
- `GET /unsigned-check` returns manifesto when unsigned, empty when all signed (including copied signatures)
- `GET /dashboard-summary` returns correct signed/total counts
- Child can read manifesto and sign → 200
- Child cannot create or update manifesto → 403
- Feedback submitted by member → owner can read it; other members cannot
- Version history returns all versions ordered by version_number desc
- All response IDs serialized as strings (SnowflakeBase)

**Verification:** `pytest tests/backend/api/test_manifesto_api.py` + `test_child_manifesto_api.py` pass; `ruff check apps/backend/` clean; `mypy apps/backend/` clean.

---

### U3. Frontend Shared Infrastructure (Types, API, SignaturePad, Viewer, Templates)

**Goal:** Create the shared frontend components and types used by all subsequent units.

**Requirements:** R1, R3, R7, R8

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/types/manifesto.ts` (new)
- `frontend/apps/main/src/api/manifesto.ts` (new)
- `frontend/apps/main/src/components/manifesto/SignaturePad.vue` (new)
- `frontend/apps/main/src/components/manifesto/BlockEditor.vue` (new)
- `frontend/apps/main/src/components/manifesto/ManifestoViewer.vue` (new)
- `frontend/apps/main/src/components/manifesto/templates/templateRegistry.ts` (new)
- `frontend/apps/main/src/components/manifesto/templates/ClassicTemplate.vue` (new)
- `frontend/apps/main/src/components/manifesto/templates/ModernTemplate.vue` (new)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add manifesto keys)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add manifesto keys)
- `frontend/apps/main/tests/unit/components/SignaturePad.spec.ts` (new)
- `frontend/apps/main/tests/unit/components/BlockEditor.spec.ts` (new)

**Approach:**
1. TypeScript types in `types/manifesto.ts`: `Manifesto`, `ManifestoVersion`, `ManifestoSignature`, `ManifestoDashboardSummary`, `ManifestoFeedback`, `TemplateDefinition`, `UnsignedManifestoCheck`.
2. API module in `api/manifesto.ts`: functions for all manifesto endpoints (create, get, sign, publish, history, feedback, dashboard-summary, unsigned-check). Follow the pattern from `api/family.ts` — `import http from './index'`.
3. `SignaturePad.vue` component:
   - Canvas element with `pointerdown`/`pointermove`/`pointerup` event handlers
   - Velocity-based stroke width (1.5px–3px) for natural handwriting feel
   - `devicePixelRatio`-aware sizing to prevent Retina blur
   - Exposes `clear()`, `isEmpty()`, `toDataURL()` via `defineExpose`
   - Props: `width`, `height`, `penColor` (default `'--color-ink'`)
   - Dark mode: uses CSS `var(--color-ink)` for stroke color
   - Clear button inside component
4. `BlockEditor.vue` component (P1-6):
   - Lightweight block editor replacing textarea for body content
   - Each block = one paragraph, rendered as a card with: `van-field` (type=textarea, autosize, single paragraph), a `van-switch` to mark as "trackable", drag handle for reordering, and a delete button
   - "+" button at bottom to add a new empty block
   - Props: `modelValue: { blocks: string[], trackableIndices: number[] }`
   - Emits: `update:modelValue` with updated blocks and trackable indices
   - Output: `{ body: string, trackable_clause_indices: number[] }` — body = blocks joined by `\n\n`
   - Used in U4 (ManifestoEditPage)
5. `ManifestoViewer.vue` component:
   - Props: `templateId`, `title`, `body`, `signatures` (array of {name, data}), `members` (array of {name, role})
   - Looks up template from registry by `templateId`, renders the template component
   - Passes title, body, and signature slots to template
   - **Null signature handling (P1-5):** when `signature.data` is `null`, renders a "✓ 已同意" glyph (via `t('manifesto.tapConsented')`) instead of an `<img>` tag. Uses `--color-success` CSS variable for the checkmark color
5. Template registry:
   - `TemplateDefinition` interface: `{ id, nameKey, lang, component }`
   - `templateRegistry.ts` exports `TEMPLATES` array and `getTemplate(id)` function
   - `getTemplatesSorted(ownerLang)` returns templates sorted by language match
6. `ClassicTemplate.vue`: Certificate style with decorative border, centered title, serif body area, signature grid at bottom.
7. `ModernTemplate.vue`: Clean layout with accent header bar, sans-serif body, horizontal signature line.
8. i18n keys: `manifesto.title`, `manifesto.sign`, `manifesto.signed`, `manifesto.pending`, `manifesto.feedback`, `manifesto.template.classic`, `manifesto.template.modern`, `manifesto.scrollHint`, `manifesto.signDeadline`, etc. All user-facing strings via `t()`.

**Patterns to follow:** `api/family.ts` for API module structure; `CelebrationAnimation.vue` for Teleport + fixed overlay pattern; `clay.css` / main app CSS vars for dark mode; `reportImage.ts` for canvas devicePixelRatio handling.

**Test scenarios:**
- `SignaturePad`: drawing produces non-empty canvas; `clear()` resets; `toDataURL()` returns valid PNG data URL
- `SignaturePad`: stroke width varies with velocity (min 1.5px, max 3px)
- `SignaturePad`: dark mode uses `--color-ink` CSS variable for stroke
- `BlockEditor`: adding a block appends to list; deleting removes it
- `BlockEditor`: toggling trackable switch on a block updates `trackable_clause_indices`
- `BlockEditor`: body output is blocks joined by `\n\n`
- `ManifestoViewer`: renders correct template based on `templateId` prop
- `ManifestoViewer`: displays all signature slots with member names
- `ManifestoViewer`: **null `signature_data` renders "✓ 已同意" glyph** (P1-5)
- Template registry: `getTemplatesSorted('zh')` returns Chinese templates first
- All i18n keys resolve in both zh-CN and en-US

**Verification:** Component tests pass; `pnpm typecheck` clean; `SignaturePad` renders correctly in both light and dark mode.

---

### U4. Main App — Owner Creation + Publish Flow

**Goal:** Build the Owner's manifesto creation wizard: template selection → content editing → preview → publish. Also covers re-publish flow (minor/major update).

**Requirements:** R1, R4, R6, R10, R11

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/pages/ManifestoTemplateSelectPage.vue` (new)
- `frontend/apps/main/src/pages/ManifestoEditPage.vue` (new)
- `frontend/apps/main/src/pages/ManifestoPreviewPage.vue` (new)
- `frontend/apps/main/src/composables/useManifestoWizard.ts` (new)
- `frontend/apps/main/src/router/index.ts` (modify — add 3 routes)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add wizard keys)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add wizard keys)

**Approach:**
1. `useManifestoWizard` composable manages cross-page state via `sessionStorage`:
   - `selectedTemplateId`, `title`, `body`, `signingDeadline`, `trackableClauseIndices`
   - `reset()` clears all state after publish or cancel
2. `ManifestoTemplateSelectPage.vue`:
   - Grid of template thumbnails (2 columns), each showing template name + preview
   - Sorted by owner language (KTD10)
   - Tap template → navigate to edit page with `templateId` in wizard state
3. `ManifestoEditPage.vue`:
   - `van-field` for title (single line, max 100 chars)
   - **`BlockEditor` component (P1-6) for body text** — replaces textarea. Each block is a paragraph card with its own `van-switch` to mark as "trackable". The BlockEditor outputs `{ body, trackable_clause_indices }` directly
   - Optional signing deadline: `van-date-picker` in a popup (can be left empty)
   - "Preview" button → navigate to preview page
   - "Switch template" link → back to template select (content preserved via wizard state)
4. `ManifestoPreviewPage.vue`:
   - Renders `ManifestoViewer` with current wizard state
   - Signature slots show member names with "待签署" placeholder
   - "Publish" button → calls `manifestoApi.create()` or `manifestoApi.publishUpdate()` → navigate back to settings
5. Re-publish flow (when editing existing manifesto):
   - After editing, show `van-action-sheet` to choose change type: "小幅修改" (minor) or "重大修改" (major)
   - Minor: calls `PATCH` with `change_type='minor'` — no re-signing needed
   - Major: calls `PATCH` with `change_type='major'` — triggers re-signing for all members
   - "影响预览" text: minor → "仅更新措辞，不需要重新签署"; major → "所有家庭成员需要重新签署"
   - Follows P4 "暂停即尊重" — bottom sheet with 200ms slow-in animation

**Patterns to follow:** `FamilyConfigPage.vue` for `van-field` form patterns; `van-action-sheet` for choice presentation; `BottomSheetConfirm.vue` (from V1 UX plan U7) for the re-publish change-type selection.

**Test scenarios:**
- Template selection navigates to edit page with correct template ID
- Edit page preserves content when switching templates
- Title length capped at 100 chars
- Preview renders selected template with title + body
- Publish creates manifesto via API and resets wizard state
- Re-publish with "minor" → API called with `change_type='minor'`
- Re-publish with "major" → API called with `change_type='major'`
- Signing deadline is optional (can be empty)
- Trackable clause toggle correctly records paragraph indices

**Verification:** Owner can create a manifesto end-to-end (select → edit → preview → publish); re-publish flow offers minor/major choice; wizard state resets after publish; `pnpm typecheck` clean.

---

### U5. Main App — Member Signing Flow + Feedback

**Goal:** Implement the forced signing popup notification + dedicated signing page for Members (P1-2), and the feedback channel ("我有想法").

**Requirements:** R3, R7, R10

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/components/manifesto/ManifestoSigningPopup.vue` (new)
- `frontend/apps/main/src/pages/ManifestoSignPage.vue` (new)
- `frontend/apps/main/src/components/manifesto/ManifestoFeedbackDialog.vue` (new)
- `frontend/apps/main/src/pages/DashboardPage.vue` (modify — integrate unsigned check)
- `frontend/apps/main/src/router/index.ts` (modify — add signing page route)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add signing + feedback keys)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add signing + feedback keys)
- `frontend/apps/main/tests/unit/components/ManifestoSigningPopup.spec.ts` (new)

**Approach:**
1. `ManifestoSigningPopup.vue` (P1-2 — popup notification, not full-screen signing):
   - `<Teleport to="body">` with `position: fixed; inset: 0; z-index: 1000`
   - `role="dialog" aria-modal="true"` for accessibility
   - Backdrop: `rgba(0,0,0,0.5)` with `backdrop-filter: blur(4px)`
   - Content: manifesto title + brief preview + CTA button "前往签署"
   - CTA click → `router.push('/manifesto/sign')` → navigate to dedicated signing page
   - Popup is dismissible via backdrop click or close button (non-blocking notification)
   - Re-appears on every app open until manifesto is signed
2. `ManifestoSignPage.vue` (dedicated signing page):
   - Full page layout with `ManifestoViewer` displaying complete manifesto content
   - Scroll gate: `IntersectionObserver` on the last content element → `hasScrolledToBottom = true`
   - Timer gate: `setTimeout(3000)` on mount → `hasWaitedLongEnough = true`
   - Sign button disabled until BOTH gates are true
   - When enabled: show `SignaturePad` in a bottom sheet, then "Confirm Sign" button
   - On confirm: calls `manifestoApi.sign({ signature_data })` → `router.back()` → refresh dashboard
   - Safety timeout: 5-second backstop to auto-enable if IntersectionObserver doesn't fire (per nprogress learning)
3. Integration in `DashboardPage.vue` (root-level check):
   - On mount/activate: call `manifestoApi.getUnsignedCheck()`
   - If unsigned manifesto exists → show `ManifestoSigningPopup`
   - If no unsigned manifesto → skip
4. `ManifestoFeedbackDialog.vue`:
   - Bottom sheet with `van-popup position="bottom"`
   - `van-field` (type=`textarea`) for feedback text
   - Submit button → calls `manifestoApi.submitFeedback({ content })`
   - Success toast + close dialog
   - Accessible from manifesto detail page (after signing) via "我有想法" button

**Patterns to follow:** `CelebrationAnimation.vue` for Teleport + fixed overlay; `MilestoneCelebration.vue` for `role="dialog"` pattern; `BottomSheetConfirm.vue` for bottom sheet; `van-popup` with safety timeout (nprogress learning).

**Test scenarios:**
- Popup appears when unsigned manifesto exists
- Popup CTA navigates to `/manifesto/sign` page
- Signing page: sign button disabled until scroll-to-bottom AND 3-second timer complete
- `IntersectionObserver` correctly detects scroll-to-bottom on signing page
- Safety timeout enables sign button after 5 seconds even without scroll
- Signature pad captures signature and submits via API
- After signing, navigates back and dashboard refreshes
- Cannot sign same version twice (API returns 409 → show "已签署" state)
- Feedback dialog submits text and shows success toast
- `prefers-reduced-motion: reduce` disables blur backdrop
- Dark mode: popup uses themed colors correctly

**Verification:** Member login with unsigned manifesto triggers popup; popup navigates to signing page; scroll + timer gate works; sign button enables correctly; feedback dialog submits; `pnpm typecheck` + tests pass.

---

### U6. Main App — Dashboard Card + Settings Management

**Goal:** Manifesto dashboard card on DashboardPage, and owner's settings management section (edit, re-publish, version history, feedback inbox).

**Requirements:** R4, R6, R9

**Dependencies:** U3, U4, U5

**Files:**
- `frontend/apps/main/src/components/dashboard/ManifestoDashboardCard.vue` (new)
- `frontend/apps/main/src/pages/FamilyConfigPage.vue` (modify — add manifesto management section)
- `frontend/apps/main/src/components/manifesto/ManifestoHistoryDialog.vue` (new)
- `frontend/apps/main/src/components/manifesto/ManifestoFeedbackList.vue` (new)
- `frontend/apps/main/src/router/index.ts` (modify — add manifesto settings route if needed)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add card + settings keys)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add card + settings keys)
- `frontend/apps/main/tests/unit/components/ManifestoDashboardCard.spec.ts` (new)

**Approach:**
1. `ManifestoDashboardCard.vue`:
   - Self-contained SFC with own data fetch (`manifestoApi.getDashboardSummary()`)
   - `van-collapse` for expand/collapse (same pattern as `SmartRemindersCard.vue`)
   - Collapsed: title + "X/Y 已签署" progress text
   - Expanded: full signer list with names + signed/pending status + timestamps
   - Self-gates visibility: `visible = false` when no active manifesto
   - Tap card → navigate to manifesto detail / settings management
2. Settings management section in `FamilyConfigPage.vue`:
   - New `van-cell-group` titled "家庭约定"
   - Cells: "查看/编辑约定" (→ edit page), "版本历史" (→ history dialog), "成员反馈" (→ feedback list with unread count badge)
   - Unread feedback count: red dot + number from `manifestoApi.getFeedback()` with `is_read=false` count
3. `ManifestoHistoryDialog.vue`:
   - `van-popup position="bottom"` with scrollable version list
   - Each version: version number, created_at, change_type badge (minor/major), title
   - Tap version → shows version detail in an expandable panel (title + body)
   - Owner-only (already gated by router)
4. `ManifestoFeedbackList.vue`:
   - List of feedback items: member name, content, timestamp, read/unread status
   - Tap to mark as read
   - Owner-only

**Patterns to follow:** `SmartRemindersCard.vue` for dashboard card self-contained pattern; `LiteracyStatusCard.vue` for collapse behavior; `FamilyConfigPage.vue` for settings cell-group layout; `van-badge` for unread count.

**Test scenarios:**
- Dashboard card shows correct signed/total count
- Card self-hides when no active manifesto exists
- Card expand/collapse works with `van-collapse`
- Settings section shows "家庭约定" group with all management cells
- Unread feedback count shows correct number
- History dialog lists all versions in descending order
- History shows change_type badges correctly
- Feedback list marks items as read on tap

**Verification:** Dashboard card displays manifesto status; settings page has management section; history dialog shows versions; feedback list works; `pnpm typecheck` + tests pass.

---

### U7. Child App — Signing Ceremony + Celebration + Homepage Summary

**Goal:** Child signing experience (age-branched), celebration integration, and homepage dynamic summary with anniversary display.

**Requirements:** R8, R9, R11

**Dependencies:** U3, U4

**Files:**
- `frontend/apps/child/src/components/manifesto/ChildManifestoPopup.vue` (new)
- `frontend/apps/child/src/pages/ManifestoSigningPage.vue` (new)
- `frontend/apps/child/src/pages/ChildHomePage.vue` (modify — add manifesto summary section + root-level unsigned check)
- `frontend/apps/child/src/components/manifesto/ManifestoSummaryCard.vue` (new)
- `frontend/apps/child/src/components/manifesto/AnniversaryDisplay.vue` (new)
- `frontend/apps/child/src/composables/useManifestoSign.ts` (new)
- `frontend/apps/child/src/api/manifesto.ts` (new)
- `frontend/apps/child/src/router/index.ts` (modify — add signing route)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify — add child manifesto keys)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify — add child manifesto keys)
- `frontend/apps/child/tests/unit/components/ManifestoSummaryCard.spec.ts` (new)

**Approach:**
1. Child API module (`api/manifesto.ts`): `getChildManifesto()`, `signChildManifesto(signatureData: string | null)`, `getTrackableClauses()`. Follow `api/family.ts` pattern.
2. `useManifestoSign` composable:
   - On init: calls `getChildManifesto()` → returns manifesto data + signing status
   - `sign(data: string | null)` → calls `signChildManifesto()` → triggers celebration on success
   - Age detection: computes from child profile `birthday` field; **age < 5 → simple branch; age ≥ 5 OR age unknown → handwriting branch** (P1-1)
3. `ChildManifestoPopup.vue` (P1-2 — popup notification in child app):
   - Clay-styled notification popup with `Teleport to="body"`
   - Shows manifesto title + brief preview in simple language + "前往签署" button
   - CTA click → `router.push('/manifesto/sign')` → navigate to signing page
   - Dismissible (non-blocking notification, re-appears on next app open)
   - Root-level check in `ChildHomePage.vue`: on mount/activate, call `getChildManifesto()`, show popup if unsigned
4. `ManifestoSigningPage.vue`:
   - Full-screen page (child app uses page-level flows for ceremony)
   - Clay-styled manifesto display: large fonts (≥18px body), brand colors, simple language
   - Age < 5 branch:
     - Option A: "同意" big button → `van-dialog` secondary confirm ("你确定要同意吗？") → **sign with `signature_data: null`** (P1-5; Viewer renders "✓ 已同意")
     - Option B: toggle to "手写签名" → shows simplified `SignaturePad` (larger stroke width for small hands)
   - Age ≥ 5 branch:
     - `SignaturePad` with standard stroke width
     - "盖章" button after signature drawn → triggers signing
   - On sign success: trigger `CelebrationAnimation` via `useCelebration.triggerCelebration()` with a synthetic "manifesto-signed" task. Show "家庭约定守护者" badge reveal via `TreasureRevealPopup`.
4. `ManifestoSummaryCard.vue` (on `ChildHomePage.vue`):
   - Section head: "我们家的约定" with arrow link to full manifesto page
   - Dynamic signer display: avatar circles + names ("爸爸、妈妈、小宝 共同约定")
   - Title excerpt (1 line) of the manifesto
   - Shown only when manifesto is signed by this child
5. `AnniversaryDisplay.vue`:
   - Below the summary card or on the manifesto detail page
   - Shows "我们的约定已经陪伴我们 N 天了" based on `signed_at` of the version
   - At 30 days / 365 days: show gentle celebration hint (small confetti CSS animation, ≤ 1500ms)
   - Uses `--color-brand-ochre` for milestone text

**Patterns to follow:** `CelebrationAnimation.vue` for celebration trigger; `TreasureRevealPopup.vue` for badge reveal; `ChildHomePage.vue` section-head layout for summary card placement; `clay.css` for Clay tokens; `motionTokens.ts` for animation durations.

**Test scenarios:**
- Child with unsigned manifesto sees popup notification on app open
- Popup CTA navigates to `/child/manifesto/sign` page
- Age < 5: "同意" button shows secondary confirm dialog, then signs with `signature_data: null`
- Age < 5: can switch to handwriting mode
- Age ≥ 5: signature pad required (no "同意" button)
- **Age unknown (no birthday): handwriting branch** (P1-1), same as age ≥ 5
- Signing triggers celebration animation
- Celebration animation ≤ 1500ms
- Homepage summary shows signer avatars + names
- Summary hidden when no manifesto or not yet signed
- Anniversary shows correct day count
- 30-day milestone shows gentle celebration
- `prefers-reduced-motion: reduce` degrades all ceremony animations
- Dark mode: uses Clay dark tokens

**Verification:** Child can sign manifesto with age-appropriate flow; celebration fires; homepage summary displays; anniversary works; `pnpm typecheck` + tests pass in child app.

---

### U8. Child App — Trackable Clause Integration

**Goal:** Connect manifesto trackable clauses to the child task page — show visual hint when trackable clauses exist.

**Requirements:** R6, R11

**Dependencies:** U2, U7

**Files:**
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — add trackable clause hint)
- `frontend/apps/child/src/composables/useTrackableClauses.ts` (new)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify — add clause hint keys)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify — add clause hint keys)

**Approach:**
1. `useTrackableClauses` composable:
   - Calls `manifestoApi.getTrackableClauses()` on init
   - Returns `{ trackableCount, hasTrackable }`
   - Caches result in `sessionStorage` (checked on page mount, refreshed on `onActivated`)
2. In `ChildTasksPage.vue`:
   - Above the task list, if `hasTrackable && chores.length > 0`: show inline hint card
   - Hint card: Clay-styled soft card with text "这个任务和我们的家庭约定有关哦"
   - No automatic task-clause linking — purely a visual reminder
   - Hint auto-hides when all chores for the day are completed

**Patterns to follow:** `ChildInlineError.vue` (from V1 UX plan U6) for Clay-styled inline card; existing `ChildTasksPage.vue` layout for insertion point.

**Test scenarios:**
- Hint appears when trackable clauses exist and tasks are present
- Hint hidden when no trackable clauses
- Hint hidden when all chores completed
- Hint uses Clay styling (no "错误" language)
- i18n keys resolve in both zh-CN and en-US

**Verification:** Trackable clause hint displays on child task page when owner marked clauses; no visual regression; `pnpm typecheck` + tests pass.

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Type check (main) | `cd frontend/apps/main && pnpm typecheck` | Main app |
| Type check (child) | `cd frontend/apps/child && pnpm typecheck` | Child app |
| Unit tests (main) | `cd frontend/apps/main && pnpm test:run` | Main app |
| Unit tests (child) | `cd frontend/apps/child && pnpm test:run` | Child app |
| Backend tests | `cd server && uv run pytest tests/backend/ -v -k manifesto` | Backend manifesto tests |
| Backend lint | `cd server && uv run ruff check apps/backend/` | Backend code |
| Backend typecheck | `cd server && uv run mypy apps/backend/` | Backend code |
| Alembic fresh DB | `cd server/apps/backend && uv run alembic upgrade head` | Migration chain |
| SnowflakeBase check | `grep -rn "class.*Response.*BaseModel" server/apps/backend/app/schemas/manifesto*.py server/apps/backend/app/schemas/manifesto/` | Should return 0 — all responses must inherit SnowflakeBase, not BaseModel |
| i18n completeness | `grep -rn "manifesto\." frontend/apps/main/src/i18n/locales/zh-CN.ts` | Should have 15+ keys |
| No hardcoded Chinese | `grep -rn "[一-鿿]" frontend/apps/main/src/components/manifesto/ frontend/apps/child/src/components/manifesto/ frontend/apps/child/src/pages/ManifestoSigningPage.vue` | Should return 0 (all strings via `t()`) |
| Animation cap | `grep -rnE "(animation|transition).*(\d{4,}ms)" frontend/apps/child/src/` | Should return 0 (>2000ms) |

---

## Definition of Done

1. All 8 implementation units pass their test scenarios.
2. `pnpm typecheck` passes in both `frontend/apps/main` and `frontend/apps/child` with 0 errors.
3. `pnpm test:run` passes in both apps with no regressions from baseline.
4. Backend: `pytest tests/backend/ -k manifesto` passes; `ruff check` clean; `mypy` clean.
5. `alembic upgrade head` succeeds on a fresh SQLite database (all 4 manifesto tables created).
6. All response schemas inherit `SnowflakeBase` (IDs serialized as strings).
7. All user-facing strings are i18n-resolved — no hardcoded Chinese in component files (grep gate).
8. All animation durations ≤ 2000ms hard cap (interaction-rules §3.2).
9. `prefers-reduced-motion: reduce` degrades all new animations to fade.
10. Dark mode: all new components use CSS modifier classes, never inline styles (dark-mode specificity learning).
11. Owner can create → preview → publish a manifesto end-to-end.
12. Member sees forced signing popup on login when unsigned manifesto exists; scroll + timer gate works.
13. Child signs with age-appropriate flow; celebration triggers on sign success.
14. Dashboard card shows signing status; self-hides when no manifesto.
15. Settings page has manifesto management section with history + feedback.
16. Trackable clause hint appears on child task page when clauses are marked.
17. No abandoned experimental code remains in the diff.
