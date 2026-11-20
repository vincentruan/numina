# Area 22 — Settings 定时任务 (统一列表 / 默认任务 / 编辑模式)

Shared conventions in [`_common.md`](../../_common.md).

Auth: adult session as `demouser` (owner).
Route: `${BASE}settings/ai/scheduled`

> 本 Area 针对 2026-11-20 定时任务合并变更：
> - 入口从「AI 助手设置」移动到「家庭管理」分组
> - `/settings/family/config` 中旧的简化定时任务滑块组已移除
> - 列表页统一展示，不再有「简洁模式 / Cron 模式」顶层页签
> - 系统默认任务在注册/迁移时写入 DB，默认启用并标记 `is_default`
> - 编辑弹窗内提供「简洁 / Cron」模式切换

---

## FS.1 — Settings 首页入口位置

```
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 「家庭管理」分组内可见「定时任务」入口，指向 `/settings/ai/scheduled`
- [ ] 「AI 助手设置」分组内不再出现「定时任务」入口
- [ ] 「家庭高级设置」入口仍可见，指向 `/settings/family/config`
- [ ] `[console]` zero errors

---

## FS.2 — 定时任务列表统一展示

```
bsk navigate ${BASE}settings/ai/scheduled --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/fs.2-scheduled-list.png
```

Assertions:
- [ ] 页面标题为「定时任务」
- [ ] 页面**没有**顶层页签「简洁模式 / Cron 模式」
- [ ] 页面显示统一任务列表，包含系统默认任务卡片
- [ ] 每个任务卡片只显示一种友好描述（如「每日 08:35」「每周日 02:00」），Cron 模式卡片不展示原始 cron
- [ ] `[console]` zero errors，`GET /api/v1/ai/scheduled-tasks` 无 500

---

## FS.3 — 系统默认内置任务正常展示

```
bsk navigate ${BASE}settings/ai/scheduled --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/fs.3-scheduled-defaults.png
```

Assertions:
- [ ] 默认任务「资产报告」可见
- [ ] 默认任务「识字周报」可见
- [ ] 两个任务均显示「默认」徽章
- [ ] 两个任务开关均为开启状态
- [ ] 「资产报告」计划显示为「每日 08:35」（cron `35 8 * * *`）
- [ ] 「识字周报」计划显示为「每周日 02:00」（cron `0 2 * * 0`）
- [ ] 状态区域可见「下次执行」/「上次执行」文案
- [ ] `[console]` zero errors

---

## FS.4 — 编辑默认任务：表单内简洁 / Cron 模式切换

```
# 在 FS.3 列表中点击「资产报告」卡片的编辑
bsk click @eN --session <id>   # 资产报告卡片「编辑」
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/fs.4-scheduled-edit-ui.png
```

Assertions:
- [ ] 编辑弹窗标题为「编辑定时任务」
- [ ] 技能字段显示「资产报告」
- [ ] 弹窗内可见「简洁 / Cron」模式切换，默认应选中「简洁」
- [ ] 简洁模式显示时/分输入与「每日/每周」频率，不显示 Cron 输入框
- [ ] 点击「Cron」后显示 Cron 表达式输入框并预填 `35 8 * * *`
- [ ] 点击「简洁」后恢复时/分输入，值为 `08:35`
- [ ] 不保存，直接关闭弹窗，任务仍为默认状态
- [ ] `[console]` zero errors

---

## FS.5 — 默认任务自定义后状态切换（可逆验证）

> 该用例会短暂修改默认任务。测试结束必须恢复原始启用状态与默认展示。
> 如环境不允许写入，可标记为 SKIP-WRITE。

```
# 在列表中关闭「识字周报」默认任务开关
bsk click @eN --session <id>   # 识字周报开关
bsk wait-ms 800ms
bsk snapshot --session <id>
# 断言后重新打开开关
bsk click @eN --session <id>   # 识字周报开关（恢复）
bsk wait-ms 800ms
```

Assertions:
- [ ] 关闭后 toast 保存成功
- [ ] 卡片徽章从「默认」变为「已自定义」
- [ ] 开关状态变为关闭
- [ ] 恢复后开关状态为开启
- [ ] 恢复后徽章仍为「已自定义」（这是预期：任何编辑都会转为自定义）
- [ ] `[console]` zero errors

---

## FS.6 — 家庭高级设置不再展示旧定时任务滑块

```
bsk navigate ${BASE}settings/family/config --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/fs.6-family-config-no-scheduled.png
```

Assertions:
- [ ] 家庭配置页正常渲染
- [ ] 不再出现「定时任务」分组
- [ ] 不再出现「月度报告日期」「月度报告时间」「每周扫描日」「每周扫描时间」等旧滑块
- [ ] AI 缓存、仪表盘阈值、金币汇率等既有配置仍可见
- [ ] `[console]` zero errors

---

## FS.7 — 网络与控制台健康检查

```
# 在 ${BASE}settings/ai/scheduled 页面
bsk evaluate --session <id> --expr "performance.getEntriesByType('resource').filter(r => r.name.includes('/ai/scheduled-tasks')).map(r => r.name)"
```

Assertions:
- [ ] `/api/v1/ai/scheduled-tasks` 请求状态为 200（无 500）
- [ ] 无 `Vue warn` / `TypeError` / `ReferenceError`
- [ ] 无 i18n key 泄露（如 `scheduledTasks.badgeDefault`）

---

## Quick Reference

| Case | 目的 | 路由 |
|------|------|------|
| FS.1 | 入口在家庭管理分组 | `/settings` |
| FS.2 | 统一列表，无顶层页签 | `/settings/ai/scheduled` |
| FS.3 | 默认任务展示 | `/settings/ai/scheduled` |
| FS.4 | 编辑弹窗模式切换 | `/settings/ai/scheduled` |
| FS.5 | 自定义状态切换 | `/settings/ai/scheduled` |
| FS.6 | 家庭配置旧滑块移除 | `/settings/family/config` |
| FS.7 | 网络/控制台健康 | `/settings/ai/scheduled` |
