---
title: "Vant 4 van-picker #option slot 图标和文本不显示"
date: 2026-10-07
last_updated: 2026-10-07
category: ui-bugs
module: frontend/apps/main
problem_type: ui_bug
component: frontend_stimulus
symptoms:
  - "Type picker popup shows neither icons nor text in Docker production"
  - "Van-picker #option slot renders empty content"
  - "Option content completely invisible despite icons correctly registered"
root_cause: wrong_api
resolution_type: code_fix
severity: medium
tags:
  - vant
  - picker
  - slot
  - destructure
  - icon-display
  - vue
  - itinerary
---

# Vant 4 van-picker #option slot 图标和文本不显示

## Problem

在旅游明细页面的"添加行程"功能中，`van-picker` 类型选择器弹出后选项内容完全空白——图标和文本均不显示。问题在 Docker 生产环境中复现。

## Symptoms

- 类型选择器弹出后，选项区域完全空白（无图标、无文本）
- 图标已通过 `register-icons.ts` 正确离线打包（排除了 Iconify 网络加载问题）
- 所有 `lucide:*` 图标在 `@iconify/json` 中存在（排除了图标数据缺失）

## What Didn't Work

- **怀疑 Iconify 网络加载/CSP 问题**：检查了 `register-icons.ts`，确认已在 `main.ts` 中导入并正确离线打包了 `lucide` 和 `mdi` 图标集
- **检查图标是否存在**：通过 Node.js 脚本验证了 `bed`, `utensils-crossed`, `car`, `map-pin`, `tag`, `plus` 等图标均存在于 `@iconify/json/json/lucide.json`
- **vue-i18n 构建错误**：`CORE_WARN_CODES_EXTEND_POINT` 导出错误是无关的 Vite 8 rolldown bug，与图标问题无关

## Solution

`ItineraryItemForm.vue` 第 222 行的 `#option` 插槽参数解构错误：

**修复前（错误）：**
```vue
<template #option="{ option }">
  <div class="type-option">
    <IIcon v-if="option.icon" :icon="option.icon" size="18" class="type-icon" />
    <span>{{ option.text }}</span>
  </div>
</template>
```

**修复后（正确）：**
```vue
<template #option="{ text, icon }">
  <div class="type-option">
    <IIcon v-if="icon" :icon="icon" size="18" class="type-icon" />
    <span>{{ text }}</span>
  </div>
</template>
```

## Why This Works

Vant 4 的 `van-picker` `#option` 插槽直接将列对象字段作为 slot props 暴露（如 `{ text, value, icon }`），**不是**嵌套在 `option` 键下。原代码解构 `{ option }` 导致 `option` 绑定为 `undefined`，所有属性访问（`option.icon`、`option.text`）静默失败。

项目中的 `SettingsPage.vue:233` 已正确使用 `{ text, value }` 解构模式，可作为参考。

## Prevention

1. **检查项目中已有的 Vant 组件插槽实现** — 在写新的 picker slot 前，先 `grep "#option"` 查找已有用法（如 `SettingsPage.vue`）
2. **查阅 Vant 4 类型定义** — 插槽 props 签名是 `{ text, value, ... }`（扁平结构），不是 `{ option: {...} }`（嵌套结构）
3. **为 picker 选项内容添加组件测试** — 断言选项的文本和图标可见，防止插槽 API 回归
4. **Vant 3→4 迁移注意** — slot prop 形状在版本间可能改变，需查阅对应版本文档

## Related Issues

- [`vant4-field-modelvalue-binding`](./vant4-field-modelvalue-binding-2026-04-08.md) — 同为 Vant 4 API 使用模式问题（`:value` vs `:model-value`）
- [`action-sheet-clipped-in-transformed-container`](./action-sheet-clipped-in-transformed-container.md) — Vant 组件 + `teleport="body"` 模式

## Files Changed

- `frontend/apps/main/src/components/travel/ItineraryItemForm.vue` (line 222)
