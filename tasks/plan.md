# Plan: API Key 明文查看 + 测试 + 质量修复

## 目标

1. 后端新增 `GET /ai/config/{id}/reveal-key` 接口（仅 owner，返回明文 API Key）
2. 前端眼睛按钮调用该接口，实现真正的明文切换
3. 补充 `mask_api_key` 单元测试
4. 优化脱敏阈值 `<= 14`
5. `aria-label` 中文字符串走 i18n

## 依赖图

```
Task 1 (后端 reveal-key 接口)
    └── Task 2 (前端 API 层 + 眼睛逻辑)
            └── Task 3 (i18n aria-label)

Task 4 (mask_api_key 阈值 + 测试) — 独立，无依赖
```

Tasks 1→2→3 串行；Task 4 可与 Task 1 并行。

## Task 1 — 后端：reveal-key 接口

**文件：** `backend/app/routers/ai_config.py`

**接口设计：**
```
GET /ai/config/{config_id}/reveal-key
权限：require_owner（仅 owner 可调用）
响应：{ "api_key": "sk-abc123..." }  HTTP 200
错误：404 配置不存在，422 无加密 key，500 解密失败
```

**实现步骤：**
1. 在 `ai_config.py` 中添加新路由，放在 `delete` 路由之后
2. 查询 `AIProviderConfig`，校验 `family_id` 归属
3. 调用 `decrypt_api_key(cfg.api_key_encrypted)`
4. 记录安全日志 `_log_security_event("ai_key_revealed", ...)`
5. 返回 `{"api_key": decrypted}`

**验证：** `uv run pytest tests/ -v -k "reveal"` 通过

---

## Task 2 — 前端：API 层 + 眼睛逻辑

**文件：**
- `frontend/apps/main/src/api/ai.ts` — 新增 `revealAIKey(configId)` 函数
- `frontend/apps/main/src/pages/AIConfigPage.vue` — 眼睛逻辑改为调用接口

**API 层：**
```ts
export const revealAIKey = (configId: string) =>
  http.get<{ api_key: string }>(`/ai/config/${configId}/reveal-key`)
```

**页面逻辑：**
- 新增 `revealedApiKey = ref<string | null>(null)` 状态
- 眼睛图标从 `v-if="editingApiKey"` 改为始终显示（有 maskedKey 时）
- 点击眼睛：
  - 若 `showApiKey` 为 false → 调用 `revealAIKey`，将明文写入 `apiKeyDisplay`，设 `showApiKey = true`
  - 若 `showApiKey` 为 true → 恢复 `apiKeyDisplay = maskedKey`，设 `showApiKey = false`，清空 `revealedApiKey`
- 用户开始输入时（`editingApiKey = true`）：眼睛切换仅控制 `type="password"/"text"`，不再调用接口
- 保存后重置：`revealedApiKey = null`，`showApiKey = false`，`apiKeyDisplay = maskedKey`

**field type 逻辑：**
```
editingApiKey && !showApiKey → 'password'
其他 → 'text'
```

**验证：** `npm run typecheck` 通过

---

## Task 3 — 前端：aria-label i18n

**文件：**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 key
- `frontend/apps/main/src/pages/AIConfigPage.vue` — 替换硬编码字符串

**新增 i18n key（放在 `aiConfig` 或 `aria` 命名空间下）：**
```ts
aiConfig: {
  hideApiKey: '隐藏 API Key',
  showApiKey: '显示 API Key',
}
```

**替换：**
```vue
:aria-label="showApiKey ? t('aiConfig.hideApiKey') : t('aiConfig.showApiKey')"
```

**验证：** `npm run typecheck` 通过

---

## Task 4 — 后端：mask_api_key 阈值 + 单元测试（独立）

**文件：**
- `backend/app/services/ai_crypto.py` — 阈值改为 `<= 14`
- `backend/tests/test_ai_crypto.py` — 新建测试文件

**阈值变更：**
```python
if len(api_key) <= 14:
    return "****"
```

**测试用例：**
```python
def test_mask_api_key_short():      # len <= 14 → "****"
def test_mask_api_key_boundary():   # len == 15 → 前6 + ******** + 后4，中间只有1位隐藏
def test_mask_api_key_typical():    # "sk-abc123def456ghi789" → "sk-abc1********i789"
def test_mask_api_key_empty():      # "" → "****"
def test_mask_api_key_exact_10():   # len == 10 → "****"
```

**验证：** `uv run pytest tests/test_ai_crypto.py -v` 全部通过

---

## Checkpoint

所有 task 完成后：
- `uv run pytest tests/ -v` 后端全绿
- `npm run typecheck` 前端无错误
- 手动验证：已保存 key → 点眼睛 → 显示明文；再点 → 恢复脱敏
