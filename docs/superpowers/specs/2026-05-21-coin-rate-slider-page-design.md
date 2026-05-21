# 星币汇率设置页面设计

## 概述

将设置页面的星币汇率配置从内联展开式改为独立页面，使用滑动条+输入框组合，滑动条拖动点复用银币/金币样式。

## 需求

- 点击"星币汇率"进入独立页面
- 页面包含两个汇率配置项：铜→银、银→金
- 每个配置项左侧为1-10刻度滑动条，右侧为输入框，双向联动
- 滑动条仅允许整数
- 滑动条拖动点：铜→银使用银币样式，银→金使用金币样式
- 页面有保存按钮，点击后提交API

## 页面结构

**路由:** `/settings/family/coin-rates`

**布局:**
- 顶部：页面标题"星币汇率设置" + 返回按钮
- 中间：两个汇率配置行（水平布局）
- 底部：保存按钮

### 每个配置行布局

```
┌───────────────────────────────────────────────┐
│ 标题：铜币兑换银币                              │
│ ┌─────────────────────┐  ┌──────────┐        │
│ │ [滑动条 1-10]       │  │ [输入框] │        │
│ │  银币图标为拖动点    │  │   10     │        │
│ │  1    5    10       │  │          │        │
│ └─────────────────────┘  └──────────┘        │
└───────────────────────────────────────────────┘
```

## 滑动条实现

- **范围:** 1–10，仅整数
- **拖动点样式:**
  - 铜→银滑动条：使用 `SilverCoin.vue` 的SVG样式
  - 银→金滑动条：使用 `GoldenCoin.vue` 的SVG样式
- **刻度标记:** 在滑动条下方显示 1、5、10 三个刻度点
- **双向联动:** 拖动滑动条更新输入框，输入框数值更新滑动条位置

## 导航流程

1. SettingsPage 点击"星币汇率"单元格 → 导航到新页面
2. CoinRatesPage 调整汇率 → 点击保存 → API调用 → toast提示 → 返回SettingsPage

## 新建组件

| 组件 | 用途 |
|------|------|
| `CoinRatesPage.vue` | 新页面，路由 `/settings/family/coin-rates` |
| `CoinSlider.vue` | 自定义滑动条组件，支持硬币样式拖动点 |

## API

使用现有API：
- **GET:** `getFamilySettings()` — 获取当前汇率配置
- **PATCH:** `updateFamilySettings({ coinCopperToSilver, coinSilverToGold })` — 更新汇率

## i18n 新增键

| 键 | 中文 | 英文 |
|----|------|------|
| `settings.coinRatesPageTitle` | 星币汇率设置 | Coin Exchange Rates |
| `settings.copperToSilverRate` | 铜币兑换银币 | Copper to Silver Rate |
| `settings.silverToGoldRate` | 银币兑换金币 | Silver to Gold Rate |

## 修改文件

| 文件 | 修改内容 |
|------|----------|
| `SettingsPage.vue` | 将内联展开式改为 `is-link to="/settings/family/coin-rates"` |
| `router/index.ts` | 添加新路由 |
| `zh-CN.ts` | 添加i18n键 |
| `en-US.ts` | 添加i18n键 |

## 验证

- 滑动条拖动时输入框实时更新
- 输入框修改时滑动条位置实时更新
- 仅允许输入1-10整数，超出范围时toast提示
- 保存成功后toast提示并返回