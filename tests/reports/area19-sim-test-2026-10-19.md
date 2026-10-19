# Numina 仿真测试报告 — Area 19: Learning OS Optimization

**日期**: 2026-10-19
**分支**: feat/learning-os-optimization

## 测试环境
- 部署模式: dev (5173 同源 dev server, cwd=frontend/apps/main)
- Base URL: http://localhost:5173/ / Child URL: http://localhost:5174/child/ / API: http://localhost:8000/api/v1
- Browser driver: browser-use (v0.1.13) → Chrome DevTools MCP (fallback after timeout)
- 服务健康: adult UP / child UP / api UP
- 前置门禁: ✓ 通过 — demouser (owner) / children 小宝,大宝,Emma / 30 assets / AI openai_compatible (active: 1)
- DB 前置: ✓ preset_learning_paths 表存在 (60 条种子数据) / alembic at lrnprst00001 (head)
- 截图目录: dogfood-output/
- 测试时间: 2026-10-19 14:30–15:00 UTC+8

## 成功摘要
- 测试用例总数: 22 (C19.1–C19.22)
- 通过: 5 (C19.3, C19.4, C19.5, C19.10, C19.18)
- 失败: 2 (C19.1, C19.8)
- 阻塞: 10 (C19.2, C19.7, C19.15, C19.16, C19.17, C19.19, C19.20, C19.21, C19.22 — 均因 P0 根因阻塞)
- 跳过: 5 (C19.6, C19.9, C19.11, C19.12, C19.13, C19.14 — 部分验证或数据不足)
- 通过用例: C19.3, C19.4, C19.5, C19.10, C19.18

## 失败详情

### C19.1 — BabyLearningPage 模块化重构 `DATA`
- **路由**: http://localhost:5173/baby/learning
- **截图**: dogfood-output/c19.1-hub-restructure.png, dogfood-output/c19.1-with-child-selected.png
- **预期表现**: 5 个模块正确渲染; 🌟 智能推荐显示推荐知识点 (API 返回 295 个 topic); 包含 child switcher; 确认派发/微调路径/换一批按钮可见
- **当前错误表现**: 模块结构正确 (5 个模块, 展开/折叠状态正确), 但 🌟 智能推荐显示空态 "暂无推荐,请稍后再试"; 无 child switcher; 无操作按钮。即使通过 Pinia store 手动设置 `selectedChildId` 后页面也不响应
- **根因**: `BabyLearningPage.vue:343` — `loadRecommendations()` 中 `if (!childId || !familyStore.aiEnabled) return` 早返回; `loadDnaGraph()` 同样守卫。页面 `onMounted` 调用 `loadData()` 时 `selectedChildId` 为 null (直接 URL 导航不经过 BabyPage); 无 `watch(babyStore.selectedChildId)` 在 ID 变化时重新拉取数据; 页面无内嵌 child selector
- **初步判断**: P0 功能缺陷 — 页面依赖外部状态初始化, 但无兜底机制。需添加: (1) watch on `selectedChildId` 变化时重新 fetch; (2) 页面内 child selector 或自动选择首个 child 的兜底逻辑

### C19.8 — 已废弃页面路由 `NAV`
- **路由**: /baby/learning/assign, /baby/learning/reviews, /baby/learning/paths
- **截图**: 无 (空白页面)
- **预期表现**: 路由返回 404 或重定向到 BabyLearningPage
- **当前错误表现**: 三个路由仍存在 (URL 不变), 但渲染为空白页面 (无组件内容, 无 404 页面, 无重定向)
- **初步判断**: 路由定义未从 router 中移除, 仅删除了对应组件文件。应在 router 配置中删除这三个 route 定义, 或添加 redirect 到 `/baby/learning`

## 阻塞用例 (P0 根因导致)

### C19.2, C19.7, C19.15, C19.16, C19.17, C19.19, C19.20, C19.21, C19.22 — `DATA` (blocked)
- **根因**: 同 C19.1 — `selectedChildId` 为 null 导致所有依赖 child 数据的模块 (推荐/图谱/审核/路径) 均显示空态
- **影响面**: 9 个用例无法验证功能正确性
- **备注**: API 层数据完整 (recommendations: 295 topics, preset paths: 60 条), 前端渲染层阻断

## 部分验证用例

### C19.6 — RecommendationsPage 微调路径 `RENDER` (部分通过)
- **路由**: /baby/learning/recommendations
- **截图**: dogfood-output/c19.6-recommendations-page.png
- **通过项**: 页面可达; 标题 "微调路径" 正确; "确认派发" 按钮存在 (disabled); "从知识图谱添加" 按钮存在
- **未通过项**: 推荐 topic 列表为空 (同 C19.1 根因)

### C19.9 — useBabyStore 跨导航持久化 (SKIP)
- 直接 URL 导航时 store 状态不保持; 从 BabyPage 选择 child 后导航可保持。需通过应用内导航测试, 当前工具链限制无法完整验证

### C19.11 — review_due 优先级 (SKIP-DATA)
- 小宝无 mastered + next_review_at ≤ now 的 topic, 无法触发 review_due 状态

### C19.12 — 知识地图标记 `DATA` (部分通过)
- 知识地图渲染正常: 6 个学科筛选芯片, topic 节点可见
- 来源标签/复习脉冲/拒绝标记为纯视觉元素 (不在 a11y tree 中), 无法通过 snapshot 断言

### C19.13, C19.14 — 拒绝反馈 (SKIP-DATA)
- 小宝无被拒绝的 topic (mastery_level ≠ "learning" after failure), 无法验证

## 通过用例详情

### C19.3 — Recommendation API ✅
- API `GET /family/learning/children/{child_id}/recommendations` 返回 `path.topics` 数组 (295 items)
- 每个 topic 含 `topic_name`, `reasons` (e.g. ["知识断点"]), `topic_id`
- 优先级排序: 知识断点 topic 排在前面

### C19.4 — PresetPathsPage ✅
- 页面正常渲染; 年级 1-6 筛选 tab; 学期 (上学期/下学期); 学科 (数学/语文/英语/科学)
- 60 条预设路径卡片正确展示 (年级1 即显示多条)
- 每条卡片显示路径名 + 知识点数量

### C19.5 — PresetPathsPage 一键派发 ✅ (交互验证)
- 点击卡片展开详情: 显示路径名 "Preset learning path for mathematics (1-2 fall)" + "66 个知识点"
- "一键派发" 按钮可见并可点击

### C19.10 — Source Tag ✅
- 儿童首页 TodayLearningCard 显示 "📝 爸妈布置" 来源标签 (uid=29_17)
- "🌟 开始新知识" 标签可见 (uid=29_10), 表示系统推荐路径

### C19.18 — Circuit Breaker API ✅
- `GET /family/learning/children/{child_id}/ai-review-status` 返回 `{"ai_auto_pass_paused": false, "consecutive_overrides": 0}`
- API 端点正常工作

## 截图清单
| 文件 | 对应用例 |
|------|----------|
| c19.1-hub-restructure.png | C19.1 |
| c19.1-with-child-selected.png | C19.1 (设置 selectedChildId 后) |
| c19.4-preset-paths.png | C19.4 |
| c19.6-recommendations-page.png | C19.6 |
| c19.7-dna-graph.png | C19.7 |
| c19.10-source-tag.png | C19.10 + 儿童首页概览 |
| c19.12-map-markers.png | C19.12 |

## 修复优先级建议

### P0 (阻断 9 个用例)
1. **BabyLearningPage selectedChildId 初始化** — 添加 watch + 兜底自动选择
   - 文件: `BabyLearningPage.vue:341-353, 389-401`
   - 方案: 在 `onMounted` 中若 `selectedChildId` 为 null, 自动选第一个 child; 添加 `watch(() => babyStore.selectedChildId, loadData)`

### P1 (路由清理)
2. **废弃路由清理** — 从 router 配置移除 /assign, /reviews, /paths
   - 文件: router 定义文件
