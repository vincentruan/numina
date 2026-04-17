---
date: 2026-04-16
id: 2026-04-16-001
title: "feat: Validation Error Field Codes"
status: active
origin: docs/brainstorms/2026-04-15-validation-error-field-codes-requirements.md
---

# Validation Error Field Codes 实现计划

## Problem Frame

FastAPI 422 响应已通过全局 `validation_error_handler` 转换为 `{field, code, msg}` 结构，但：
1. 后端 `_VALIDATION_CODE_MAP` 仅覆盖 7 种 Pydantic error type，缺少 `REQUIRED`/`INVALID_VALUE`/`INVALID_FORMAT`/`INVALID_TYPE` 的 locale 消息
2. 前端 interceptor 读取 `details` 但只 join 成 toast，无字段级路由机制
3. 没有任何表单页面消费字段级错误

目标：补全后端 locale 消息，新增前端 `useValidationErrors` composable，在 `RegisterPage.vue` 作为参考实现接入字段级展示。

(see origin: docs/brainstorms/2026-04-15-validation-error-field-codes-requirements.md)

## Scope

**In scope:**
- 后端：补全 `_VALIDATION_CODE_MAP` 缺失的 locale 消息（`REQUIRED`、`INVALID_VALUE`、`INVALID_FORMAT`、`INVALID_TYPE`）
- 后端：扩展 `_VALIDATION_CODE_MAP` 覆盖更多常见 Pydantic v2 error type
- 前端：`useValidationErrors` composable（provide/inject 模式）
- 前端：`RegisterPage.vue` 接入字段级错误展示（参考实现）
- 后端测试：`validation_error_handler` 的字段映射覆盖

**Out of scope:**
- 其他表单页面（`AssetFormPage.vue`、`LiabilityFormPage.vue` 等）——机制建立后各页面按需接入
- 前端表单验证库（vee-validate 等）
- 嵌套对象字段路径处理

## Architecture Decisions

### 1. 后端：ValidationCode 独立于 ErrorCode

`_VALIDATION_CODE_MAP` 中的 code 字符串（`REQUIRED`、`TOO_SHORT` 等）不加入 `ErrorCode` enum——它们是字段级校验码，与业务错误码是不同维度。locale key 使用 `VALIDATION_<CODE>` 前缀与业务错误码区分。

### 2. 前端：provide/inject 而非 Pinia store

`validationErrors` 是表单级瞬态状态，不需要跨组件持久化。`useValidationErrors` composable 在表单页面 `provide`，子组件 `inject`。每次新请求前清空，422 响应后填充。

### 3. 前端：interceptor 保持 toast fallback

422 处理逻辑：先填充 `validationErrors`（若 composable 已 provide），再 toast 拼接消息作为 fallback。不消费 composable 的页面行为不变。

**决策：interceptor 不直接感知 composable**——interceptor 抛出 error，页面在 catch 块中调用 `setErrors(error)`。这样 interceptor 保持无状态，composable 由页面控制生命周期。

## Implementation Units

### Unit 1: 后端 — 补全 locale 消息

**Files:**
- `backend/app/errors/locales/zh-CN.json` — 新增 4 条 VALIDATION_* 消息
- `backend/app/errors/locales/en-US.json` — 新增 4 条 VALIDATION_* 消息

**Changes:**
- `VALIDATION_REQUIRED`: `"此字段为必填项"` / `"This field is required"`
- `VALIDATION_INVALID_VALUE`: `"输入值无效"` / `"Invalid value"`
- `VALIDATION_INVALID_FORMAT`: `"格式不正确"` / `"Invalid format"`
- `VALIDATION_INVALID_TYPE`: `"类型不正确"` / `"Invalid type"`

**Note:** `TOO_SHORT`/`TOO_LONG`/`VALIDATION_ERROR` 已存在，不重复添加。

**Test file:** `backend/tests/test_validation_errors.py`

**Test scenarios:**
- `missing` field → `code="REQUIRED"`, `msg="此字段为必填项"`（zh-CN）
- `string_too_short` with ctx → `code="TOO_SHORT"`, `msg="长度至少 N 位"`
- `string_pattern_mismatch` → `code="INVALID_FORMAT"`, `msg="格式不正确"`
- `int_type` → `code="INVALID_TYPE"`, `msg="类型不正确"`
- 未知 Pydantic type → `code="INVALID_VALUE"`

---

### Unit 2: 后端 — 扩展 _VALIDATION_CODE_MAP

**Files:**
- `backend/app/error_handlers.py` — 扩展 `_VALIDATION_CODE_MAP`

**Additional mappings to add** (common Pydantic v2 types not yet covered):
```
"string_type": "INVALID_TYPE",
"bool_type": "INVALID_TYPE",
"int_parsing_error": "INVALID_TYPE",
"float_parsing_error": "INVALID_TYPE",
"greater_than": "INVALID_VALUE",
"greater_than_equal": "INVALID_VALUE",
"less_than": "INVALID_VALUE",
"less_than_equal": "INVALID_VALUE",
"enum": "INVALID_VALUE",
"url_type": "INVALID_FORMAT",
"datetime_type": "INVALID_FORMAT",
```

**Test scenarios** (append to `test_validation_errors.py`):
- `string_type` → `INVALID_TYPE`
- `enum` → `INVALID_VALUE`
- `greater_than` → `INVALID_VALUE`

---

### Unit 3: 前端 — useValidationErrors composable

**Files:**
- `frontend/src/composables/useValidationErrors.ts` — 新建

**Interface:**
```typescript
// ValidationError matches backend details item
interface ValidationError { code: string; msg: string }

// composable returns:
{
  validationErrors: Ref<Record<string, ValidationError>>,
  setErrors: (axiosError: unknown) => void,  // parses 422 details
  clearErrors: () => void,
  getError: (field: string) => ValidationError | undefined,
}
```

**Behavior:**
- `setErrors(err)`: 若 `err.response?.status === 422` 且 `data.details` 存在，将 details 数组转为 `{ [field]: {code, msg} }` map
- `clearErrors()`: 重置为空对象
- `getError(field)`: 返回对应字段的错误，无则 undefined
- provide key: `Symbol('validationErrors')` — 导出为具名常量供 inject 使用

**Test file:** `frontend/src/composables/useValidationErrors.test.ts`

**Test scenarios:**
- `setErrors` with 422 response → populates map correctly
- `setErrors` with non-422 → no-op
- `clearErrors` → resets to empty
- `getError('password')` → returns correct entry

---

### Unit 4: 前端 — RegisterPage.vue 参考实现

**Files:**
- `frontend/src/pages/RegisterPage.vue` — 接入 `useValidationErrors`

**Changes:**
- `provide` composable 实例
- 在 `catch` 块调用 `setErrors(err)`，在提交前调用 `clearErrors()`
- 在 `username`、`password`、`family_name` 字段下方条件渲染错误消息（使用 `getError(field)?.msg`）
- 使用 Vant `<van-field>` 的 `:error-message` prop 或字段下方 `<div class="field-error">` 展示

**Pattern to follow:** 参考 `frontend/src/pages/LoginPage.vue` 的表单结构和错误展示方式

**Test scenarios** (manual / E2E):
- 提交空表单 → 各字段下方显示"此字段为必填项"
- 提交过短密码 → password 字段下方显示"长度至少 N 位"
- 提交重复用户名 → toast 显示业务错误（非字段级，走现有 AppError 路径）

---

## Sequencing

```
Unit 1 (locale 消息) ──┐
Unit 2 (code map 扩展) ─┤ 均独立，可并行
                        ↓
              Unit 3 (composable)
                        ↓
              Unit 4 (RegisterPage 接入)
```

Unit 1 和 Unit 2 无依赖关系，可并行。Unit 3 不依赖后端变更（纯前端）。Unit 4 依赖 Unit 3。

## Existing Patterns to Follow

- **error_handlers.py**: `_VALIDATION_CODE_MAP` 和 `validation_error_handler` 已存在，直接扩展
- **locale 文件**: 参考现有 `VALIDATION_TOO_SHORT` 格式，key 使用 `VALIDATION_<CODE>` 前缀
- **composable 结构**: 参考 `frontend/src/composables/useAuth.ts` — `ref` + 返回对象
- **表单错误展示**: 参考 Vant `<van-field>` 的 `error-message` prop（已在项目中使用）
- **测试**: 后端参考 `backend/tests/test_auth.py` fixture 模式；前端参考 vitest + `@vue/test-utils`

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Pydantic v2 `ctx` 字段在某些 error type 中不存在 | `ctx = error.get("ctx", {})` 已有防御，fallback 到 `error.get("msg", code)` |
| 前端 interceptor 与 composable 解耦导致时序问题 | 页面在 catch 块调用 `setErrors`，不依赖 interceptor 内部状态 |
| RegisterPage 表单结构与 Vant field 不兼容 | 先读 LoginPage.vue 确认现有模式再实现 |

## Test Coverage Summary

| Unit | Test File | Scenarios |
|------|-----------|-----------|
| 1+2 | backend/tests/test_validation_errors.py | 各 Pydantic type 映射、locale 消息、fallback |
| 3 | frontend/src/composables/useValidationErrors.test.ts | setErrors、clearErrors、getError |
| 4 | 手动验证 | 字段级展示、toast fallback |
