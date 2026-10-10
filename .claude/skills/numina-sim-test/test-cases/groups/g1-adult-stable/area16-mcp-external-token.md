# Area 16 — MCP External API Token & Governance (外部 MCP 令牌与治理)

Shared conventions in [`_common.md`](../../_common.md).

Auth: adult session as `demouser` (owner)。另需 member 角色账户 (M16.4.x 权限边界)。
本 Area 覆盖 Issue #118 的两个阶段:

- **Phase 1** (M16.1 – M16.7): Backend MCP 外部 API Token 生命周期、认证、两级访问控制、前端管理卡片
- **Phase 2** (M16.8 – M16.15): Per-tool 白名单、审计日志、速率限制、异常检测、统计面板

> **运行时机:** G1 内排在 area14 (travel) 之后, area8 (expanded features) 之前。
> 本 Area 依赖 AI provider 已启用 (Phase 1 F2 流程需要 MCP 工具可调用)。
> 部分用例 (M16.4.x) 需要 member 角色账户, 当前标记为 deferred。

> **API 测试说明:** 本 Area 大量使用 `curl` 直接验证后端行为 (SSE 连接、token 认证、
> 速率限制), 因为 MCP 协议交互无法纯浏览器驱动。浏览器部分覆盖前端 UI。

---

## 前置: MCP Token 准备 (Phase 0 扩展)

在 Phase 1.5 门禁中增加 MCP token 前置检查:

```bash
# 检查是否已有 MCP token; 如无, 通过 API 生成一个供后续测试使用
MCP_TOKEN_RESP=$(curl -s -H "$AUTH" -X POST "${API_BASE}/ai/mcp-token")
MCP_TOKEN=$(echo "$MCP_TOKEN_RESP" | jq -r '.data.token // empty')
if [ -z "$MCP_TOKEN" ]; then
  echo "GATE FAIL: cannot generate MCP token for testing"
  exit 1
fi
echo "  (MCP test token generated: ${MCP_TOKEN:0:8}••••${MCP_TOKEN: -4})"

# 启用 allow_external 供后续读取测试
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": true}' > /dev/null
```

> **注意:** 测试结束后 (Phase 5 cleanup) 需要 DELETE token 清理。

---

## M16.1 — Token 生命周期: 首次生成 (Phase 1, F1)

Route: `/settings/ai/mcp`
Component: `BackendMCPCard.vue`
API: `POST /api/v1/ai/mcp-token`

### M16.1.1 无 token 时卡片初始状态

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.1.1-mcp-card-empty.png
```

Assertions:
- [ ] "Backend MCP" 卡片渲染, 与 "系统内置" 标签视觉区分
- [ ] 无 token 时显示 "生成令牌" / "Generate Token" 按钮
- [ ] 无 token 掩码显示区域
- [ ] `[console]` zero errors

### M16.1.2 首次生成 token

```
# 点击 "生成令牌" 按钮
bsk snapshot --session <id>   # 获取按钮 ref
bsk click @eN --session <id>  # 点击生成
# 确认对话框弹出 (如有)
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.1.2-mcp-token-generated.png
```

Assertions:
- [ ] 生成后卡片显示掩码 token (`mcp_••••••••••••abcd`)
- [ ] 显示 "令牌已生成 — 请立即复制, 不会再次显示" 提示
- [ ] 复制按钮可用
- [ ] 过期时间选择器默认为 "永不过期"
- [ ] `allow_external` 和 `allow_write` 开关默认关闭
- [ ] `[console]` zero errors

### M16.1.3 API 验证: 生成返回明文

```bash
# 用 curl 直接调用 (清除刚才浏览器生成的 token, 重新测试)
curl -s -H "$AUTH" -X DELETE "${API_BASE}/ai/mcp-token"  # 先清除
RESP=$(curl -s -H "$AUTH" -X POST "${API_BASE}/ai/mcp-token")
echo "$RESP" | jq '.data'
```

Assertions:
- [ ] 响应 HTTP 201
- [ ] `data.token` 以 `mcp_` 开头, 总长度 47 字符 (`mcp_` + 43 random chars)
- [ ] `data.token_prefix` 为 token 前 8 字符
- [ ] `data.token_last4` 为 token 后 4 字符
- [ ] `data.allow_external == false`
- [ ] `data.allow_write == false`
- [ ] `data.is_active == true`
- [ ] `data.expires_at == null`
- [ ] 再次 GET 同一 token: `data.token` 字段不存在 (仅生成时返回一次)

---

## M16.2 — Token 显示与交互 (Phase 1, R16-R19)

Route: `/settings/ai/mcp`
Component: `BackendMCPCard.vue`

### M16.2.1 Token 掩码显示

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Token 默认显示为 `mcp_••••••••••••{last4}` 格式
- [ ] 眼睛图标 (eye toggle) 可见

### M16.2.2 眼睛切换显示明文 + 10s 自动遮罩

```
# 点击眼睛图标
bsk click @eN --session <id>   # eye toggle ref
bsk snapshot --session <id>
```

Assertions:
- [ ] 点击后显示完整明文 token
- [ ] 10 秒后重新 snapshot → token 恢复掩码显示
- [ ] `[console]` zero errors

### M16.2.3 复制到剪贴板

```
bsk snapshot --session <id>
# 点击复制按钮
bsk click @eN --session <id>   # copy button ref
bsk snapshot --session <id>
```

Assertions:
- [ ] 复制后显示成功 toast
- [ ] `[console]` zero errors

> 剪贴板内容无法直接从 bsk 验证, 依赖 API 测试覆盖。

### M16.2.4 过期时间选择器

```
# 点击过期时间字段
bsk snapshot --session <id>
bsk click @eN --session <id>   # expiration field ref
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.2.4-expiration-picker.png
```

Assertions:
- [ ] 弹出 `van-popup` + `van-picker` 底部选择器
- [ ] 选项包含: 30 天 / 90 天 / 180 天 / 1 年 / 自定义日期 / 永不过期
- [ ] 选择 "30 天" → 关闭 popup → 卡片显示新的过期时间
- [ ] `[console]` zero errors

---

## M16.3 — 外部 MCP SSE 连接与认证 (Phase 1, R5-R9)

API: `GET /api/v1/mcp/public/{family_id}/sse`, `POST /api/v1/mcp/public/messages`

> **注意:** 以下测试使用 `curl` 直接验证, 不需要浏览器。
> `$FAMILY_ID` 从 `curl -s -H "$AUTH" "$API_BASE/auth/me" | jq -r '.data.family_id'` 获取。

### M16.3.1 Bearer token 认证连接

```bash
FAMILY_ID=$(curl -s -H "$AUTH" "${API_BASE}/auth/me" | jq -r '.data.family_id')

# 使用 Bearer header 连接 SSE (5s 超时, 只验证连接建立)
timeout 5 curl -sf -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true
```

Assertions:
- [ ] HTTP 200 (SSE 连接建立成功)
- [ ] 响应 Content-Type 包含 `text/event-stream`

### M16.3.2 无效 token → 401

```bash
timeout 5 curl -s -N \
  -H "Authorization: Bearer mcp_invalid_token_xxxxxxxxxxxxx" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true
```

Assertions:
- [ ] HTTP 401

### M16.3.3 allow_external=False → 403

```bash
# 先关闭 allow_external
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": false}' > /dev/null

# 尝试连接
timeout 5 curl -s -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true

# 恢复 allow_external
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": true}' > /dev/null
```

Assertions:
- [ ] HTTP 403

### M16.3.4 过期 token → 401

```bash
# 设置 token 过期时间为过去 (通过 PATCH expires_at)
# 注意: 这需要 API 支持设置过去时间; 如果不支持, 通过 DB 直接修改测试
PAST_DATE=$(date -u -v-1d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "yesterday" +"%Y-%m-%dT%H:%M:%SZ")
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d "{\"expires_at\": \"${PAST_DATE}\"}" > /dev/null

# 尝试连接
timeout 5 curl -s -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true

# 恢复: 清除过期时间
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"expires_at": null}' > /dev/null
```

Assertions:
- [ ] HTTP 401

### M16.3.5 Query param 认证 → 连接成功 + 审计 WARNING

```bash
# 使用 ?token= 方式连接
timeout 5 curl -sf -N \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse?token=${MCP_TOKEN}" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true
```

Assertions:
- [ ] HTTP 200 (连接成功)
- [ ] 后端日志中出现 WARNING: 包含 family_id 和 token prefix
  (需检查 backend 日志: `docker logs numina-backend 2>&1 | grep "query param" | tail -1`)

### M16.3.6 已撤销 token → 401

```bash
# 生成新 token (旋转), 旧 token 应该失效
OLD_TOKEN="$MCP_TOKEN"
NEW_RESP=$(curl -s -H "$AUTH" -X POST "${API_BASE}/ai/mcp-token")
MCP_TOKEN=$(echo "$NEW_RESP" | jq -r '.data.token')

# 旧 token 连接
timeout 5 curl -s -N \
  -H "Authorization: Bearer $OLD_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true

# 新 token 连接
timeout 5 curl -sf -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true
```

Assertions:
- [ ] 旧 token → HTTP 401
- [ ] 新 token → HTTP 200

### M16.3.7 User-Agent 控制字符清洗 (P3 修复验证)

> 验证入口端清洗 User-Agent 中的 C0/C1 控制字符, 防止日志注入攻击。
> 恶意 UA 如 `"Mozilla\nINFO  [fake] injected log line"` 不应被原样写入审计日志。

```bash
# 1. 发送包含控制字符的 User-Agent
MALICIOUS_UA=$'Mozilla/5.0\r\nX-Injected: fake-log-line'
timeout 3 curl -sf -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "User-Agent: ${MALICIOUS_UA}" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null 2>/dev/null || true

# 等待审计写入
sleep 2

# 2. 查询审计日志中的 user_agent 字段
LOGS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?event_type=connect&page_size=1")
echo "$LOGS" | jq -r '.data.items[0].user_agent'
```

Assertions:
- [ ] 审计日志中 `user_agent` 不包含 `\n`, `\r` 等控制字符
- [ ] 控制字符被替换为空格或被剥离
- [ ] 可打印 ASCII 部分保留 (如 "Mozilla/5.0")
- [ ] 代码审查: `mcp_public.py` 入口处有 `user_agent.replace("\n", " ").replace("\r", " ")` + 控制字符过滤

---

## M16.4 — 两级访问控制 (Phase 1, R5, R12)

API: `tools/list` via MCP protocol

> 以下验证工具列表在不同 access 配置下的行为。
> 使用 MCP JSON-RPC 协议通过 SSE + messages 端点交互。

### M16.4.1 allow_external=True, allow_write=False → 仅读工具

```bash
# 确保 allow_external=True, allow_write=False
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": true, "allow_write": false}' > /dev/null

# 连接 SSE 获取 session endpoint, 发送 tools/list
# (SSE 连接获取 session_url 后发送 JSON-RPC)
# 简化: 通过 stats API 间接验证 (或手动 SSE 交互)
```

Assertions:
- [ ] `tools/list` 返回 12 个读工具 (`get_*` 系列, `requires_write=False`)
- [ ] `tools/list` 不包含写工具 (`import_*`, `record_*` 系列)

### M16.4.2 allow_write=True → 包含写工具

```bash
# 开启 allow_write
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_write": true}' > /dev/null

# 重新 tools/list
```

Assertions:
- [ ] `tools/list` 返回全部 16 个工具 (12 读 + 4 写)
- [ ] 写工具包含: `import_assets_batch`, `import_liabilities_batch`, `import_credit_cards_batch`, 及第四个写工具

```bash
# 恢复: 关闭 allow_write
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_write": false}' > /dev/null
```

### M16.4.3 前端 allow_external 开关确认对话框

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 点击 allow_external 开关
bsk click @eN --session <id>   # allow_external toggle ref
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.4.3-allow-external-confirm.png
```

Assertions:
- [ ] 弹出确认对话框, 包含安全警告 (列出暴露的数据范围)
- [ ] 确认后开关切换, 显示成功 toast
- [ ] `[console]` zero errors

### M16.4.4 前端 allow_write 开关确认对话框

```
# 在 allow_external 已开启的前提下
bsk snapshot --session <id>
# 点击 allow_write 开关
bsk click @eN --session <id>   # allow_write toggle ref
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.4.4-allow-write-confirm.png
```

Assertions:
- [ ] 弹出确认对话框, 包含写操作安全警告
- [ ] 确认后开关切换, 显示成功 toast
- [ ] `[console]` zero errors

---

## M16.5 — 合成用户隔离 (Phase 1, R4)

API: `GET /api/v1/family/members`, `POST /api/v1/auth/login`

### M16.5.1 合成用户不在成员列表中

```bash
# 获取家庭成员列表
MEMBERS=$(curl -s -H "$AUTH" "${API_BASE}/family/members")
echo "$MEMBERS" | jq '.data[] | .role'
```

Assertions:
- [ ] 成员列表中不包含 `role == "external_token"` 的用户
- [ ] 仅显示人类成员 (owner + adult + child)

### M16.5.2 合成用户无法登录

```bash
# 尝试用合成用户名登录 (用户名通常是 family_mcp_token_{family_id} 或类似)
# 由于合成用户没有密码, 登录应失败
LOGIN_RESP=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"mcp_service_xxx","password":"any"}')
echo "$LOGIN_RESP" | jq '.code'
```

Assertions:
- [ ] 返回 `AUTH_INVALID_CREDENTIALS` 错误 (与普通错误凭证相同)
- [ ] 不泄露合成用户存在的信息

### M16.5.3 合成用户 role 字段长度 (仿真测试 bug 修复验证)

> 仿真测试发现: `users.role` 列在 DB 中为 `VARCHAR(10)`,
> 但 `external_token` 有 14 字符, 导致 `DataError: value too long for type character varying(10)`。
> 修复: 迁移 mcp001 将列扩展为 `VARCHAR(20)`, 模型同步更新。

```bash
# 1. 删除现有 token (如有), 重新生成以触发合成用户创建
curl -s -H "$AUTH" -X DELETE "${API_BASE}/ai/mcp-token" > /dev/null 2>&1
RESP=$(curl -s -H "$AUTH" -X POST "${API_BASE}/ai/mcp-token" -w "\n%{http_code}")
HTTP_CODE=$(echo "$RESP" | tail -1)
echo "Generate token after synthetic user creation: HTTP $HTTP_CODE"

# 2. 验证合成用户存在于数据库 (通过 API 间接验证)
# 合成用户不应出现在成员列表中 (M16.5.1 已覆盖)
# 但 token 生成成功意味着合成用户创建成功 (role='external_token' 写入无报错)
```

```bash
# 3. 直接检查数据库列定义 (代码审查)
cd server && .venv/bin/python -c "
from sqlalchemy import text
from apps.backend.app.database import SessionLocal
db = SessionLocal()
result = db.execute(text(\"SELECT character_maximum_length FROM information_schema.columns WHERE table_name='users' AND column_name='role'\"))
length = result.scalar()
print(f'users.role: VARCHAR({length})')
assert length >= 20, f'role column too short: VARCHAR({length}), need >= 20 for external_token'
db.close()
"
```

Assertions:
- [ ] `POST /ai/mcp-token` 返回 201 (不是 500 DataError)
- [ ] 合成用户 `role='external_token'` (14 字符) 成功写入数据库
- [ ] `users.role` 列在 DB 中为 `VARCHAR(20)` (迁移 mcp001 已应用)
- [ ] 模型定义 `String(20)` 与 DB schema 一致

---

## M16.6 — 内部 MCP 路径不受影响 (Phase 1, R21-R23)

### M16.6.1 内部 agent JWT 路径仍工作

```bash
# 内部 MCP 路径使用 X-Agent-Token (由 agent 模块获取)
# 验证端点存在且不接受外部 token
timeout 5 curl -s -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/internal/mcp/${FAMILY_ID}/sse" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || true
```

Assertions:
- [ ] 内部路径不接受 Bearer token (返回 401 — 它只接受 JWT agent token)
- [ ] 内部路径的代码路径未引入 `mcp_public` 模块 (代码审查)

### M16.6.2 bootstrap 系统 MCP server 记录不变

```bash
# 检查 /ai/mcp-servers 列表中 backend 类型的 server 仍存在且不可删除
SERVERS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-servers")
echo "$SERVERS" | jq '[.data[] | select(.mcp_type == "backend")] | length'
```

Assertions:
- [ ] `mcp_type="backend"` 的系统记录仍然存在
- [ ] 不可通过用户 CRUD 删除 (无 DELETE 端点或返回 403/400)

---

## M16.7 — Token 轮转与撤销 (Phase 1, R3, R13)

Route: `/settings/ai/mcp`
API: `POST /api/v1/ai/mcp-token` (rotation), `DELETE /api/v1/ai/mcp-token`

### M16.7.1 前端轮转确认对话框

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 点击 "重新生成" / "Regenerate" 按钮
bsk click @eN --session <id>
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.7.1-rotate-confirm.png
```

Assertions:
- [ ] 弹出确认对话框: "旧令牌将立即失效, 是否继续?"
- [ ] 确认后新 token 生成, 卡片显示新的掩码 token
- [ ] 旧的 "copy now" 提示重新出现
- [ ] `[console]` zero errors

### M16.7.2 撤销 token (DELETE)

```bash
# DELETE 撤销
curl -s -H "$AUTH" -X DELETE "${API_BASE}/ai/mcp-token" -w "%{http_code}" -o /dev/null
```

Assertions:
- [ ] HTTP 204 (No Content)
- [ ] 随后 GET 返回 404 (无 token)
- [ ] 外部连接使用被撤销的 token → 401

### M16.7.3 撤销后前端状态

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 卡片回到 "生成令牌" 按钮状态 (M16.1.1 初始状态)
- [ ] 无掩码 token 显示
- [ ] `[console]` zero errors

---

## M16.8 — Per-Tool 白名单 (Phase 2, P2-R1 — P2-R3)

Route: `/settings/ai/mcp` → 工具权限 popup
API: `PATCH /api/v1/ai/mcp-token` with `allowed_tools`

### M16.8.1 默认 allowed_tools=null → 全部可用

```bash
# 确认当前 allowed_tools 为 null
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'
```

Assertions:
- [ ] `allowed_tools == null`
- [ ] 前端卡片显示 "全部可用（未限制）" 或 "All tools available"

### M16.8.2 前端工具权限弹窗 — 全选状态

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 点击 "工具权限" 行
bsk click @eN --session <id>   # tool permissions row ref
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.8.2-tool-permissions-popup.png
```

Assertions:
- [ ] 弹出 `van-popup position="bottom"` 弹窗
- [ ] 显示所有读工具 (12 个) 的 checkbox, 全部选中
- [ ] 如果 `allow_write=True`, 还显示写工具 (4 个) 带 🔒 图标
- [ ] 如果 `allow_write=False`, 写工具不显示
- [ ] 顶部有 "全部启用" 和 "清空" 快捷按钮
- [ ] `[console]` zero errors

### M16.8.3 取消勾选一个工具并保存

```
# 在弹窗中取消勾选一个工具 (如 get_recent_alerts)
bsk snapshot --session <id>
bsk click @eN --session <id>   # uncheck specific tool
# 点击保存
bsk click @eN --session <id>   # save button
bsk snapshot --session <id>
```

Assertions:
- [ ] PATCH 请求发送 `allowed_tools: [11 tools]` (不含取消的那个)
- [ ] 卡片显示 "11 / 12 已启用" 或类似计数
- [ ] `[console]` zero errors

### M16.8.4 API: 无效工具名 → 400

```bash
curl -s -X PATCH "${API_BASE}/ai/mcp-token" \
  -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"allowed_tools": ["nonexistent_tool"]}' | jq '.'
```

Assertions:
- [ ] HTTP 400
- [ ] 错误消息包含 "invalid tool name: nonexistent_tool"

### M16.8.5 API: allowed_tools=null 重置为全部可用

```bash
# 先设置一个子集
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allowed_tools": ["get_assets"]}' > /dev/null

# 验证
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'

# 重置为 null
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allowed_tools": null}' > /dev/null

# 验证恢复
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'
```

Assertions:
- [ ] 设置后: `allowed_tools == ["get_assets"]`
- [ ] 重置后: `allowed_tools == null`

### M16.8.6 API: allowed_tools=[] 表示无工具

```bash
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allowed_tools": []}' > /dev/null
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'

# 恢复
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allowed_tools": null}' > /dev/null
```

Assertions:
- [ ] `allowed_tools == []` (空数组, 不是 null)

### M16.8.7 前端 "全部启用" → PATCH null

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
# 先设置一个子集 (如果 M16.8.3 已执行)
# 打开工具权限弹窗
bsk click @eN --session <id>
bsk snapshot --session <id>
# 点击 "全部启用"
bsk click @eN --session <id>   # "全部启用" button
bsk snapshot --session <id>
```

Assertions:
- [ ] PATCH 发送 `allowed_tools = null`
- [ ] 卡片恢复显示 "全部可用（未限制）"
- [ ] `[console]` zero errors

### M16.8.8 隐藏写工具不被保存到后端 (P1 修复验证)

> 当 `allow_write=False` 时，写工具从弹窗中隐藏。
> 验证：如果之前的选中状态包含写工具，保存时这些写工具会被过滤掉，不会发送到后端。

```bash
# 1. 先开启 allow_write，选择包含写工具的子集
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_write": true, "allowed_tools": ["get_assets", "import_assets_batch"]}' > /dev/null

# 验证: allowed_tools 包含写工具
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'
# Expected: ["get_assets", "import_assets_batch"]

# 2. 关闭 allow_write
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_write": false}' > /dev/null
```

```
# 3. 前端: 打开工具权限弹窗 (写工具不可见)
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # 工具权限行
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.8.8-hidden-write-tools.png
# 点击保存 (不修改选中状态)
bsk click @eN --session <id>   # 保存按钮
```

```bash
# 4. 验证: PATCH 请求中不包含写工具 (通过 API 确认)
# 前端应过滤掉隐藏工具, 仅发送可见工具
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" | jq '.data.allowed_tools'
```

Assertions:
- [ ] `allow_write=False` 后弹窗中不显示写工具 (带 🔒 标记的)
- [ ] 保存后 `allowed_tools` 中不包含 `import_assets_batch` (被前端过滤)
- [ ] PATCH 请求 payload 中不含写工具名 (可通过 Network tab 确认)
- [ ] `[console]` zero errors

---

## M16.9 — 审计日志写入 (Phase 2, P2-R4 — P2-R8)

API: `GET /api/v1/ai/mcp-token/access-logs`

### M16.9.1 外部连接产生 connect 事件

```bash
# 确保 allow_external=True
curl -s -H "$AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": true}' > /dev/null

# 外部连接 SSE (短暂连接)
timeout 3 curl -sf -N \
  -H "Authorization: Bearer $MCP_TOKEN" \
  "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
  -o /dev/null 2>/dev/null || true

# 等待审计写入 (异步)
sleep 2

# 查询审计日志
LOGS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?event_type=connect&page_size=5")
echo "$LOGS" | jq '.data.items[0]'
```

Assertions:
- [ ] 存在 `event_type == "connect"` 的记录
- [ ] 记录包含 `family_id`, `session_id`, `client_ip`, `created_at`
- [ ] `created_at` 为近期时间 (1 分钟内)

### M16.9.2 工具调用产生 tool_call 事件

> 需要通过 MCP 协议发送 `tools/call` JSON-RPC 请求。
> 简化: 使用 stats API 间接验证 (M16.12)。

Assertions (通过 API 间接验证):
- [ ] 如果有工具调用, `mcp_access_logs` 存在 `event_type == "tool_call"` 的记录
- [ ] 记录包含 `tool_name`, `status`, `duration_ms`

### M16.9.3 内部 agent 路径不产生审计行

```bash
# 内部 agent 调用 MCP 工具 (通过正常 AI chat 流程触发工具调用)
# 然后检查 mcp_access_logs 是否增加了行
BEFORE=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?page_size=1" | jq '.data.total')
# (内部 agent 调用需要 AI 启用 + 触发工具; 简化为检查 callback=None 的代码路径)
# 通过代码审查确认: mcp_internal.py 构造 MCPSession 时不传 audit_callback
```

Assertions:
- [ ] 内部 agent 路径不向 `mcp_access_logs` 写入行 (代码审查 + 单元测试覆盖)
- [ ] `audit_callback` 默认为 `None`

### M16.9.4 args_digest 密钥脱敏

```bash
# 如果有包含敏感参数的工具调用, 检查 args_digest
# 通过 DB 直接查询 (或 API 返回) 验证
LOGS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?event_type=tool_call&page_size=10")
echo "$LOGS" | jq '[.data.items[] | select(.args_digest != null)] | .[0].args_digest'
```

Assertions:
- [ ] `args_digest` 中不包含 `mcp_` 开头的明文 token
- [ ] `args_digest` 中不包含 `Bearer` 开头的 token
- [ ] 匹配密钥模式 (`password`, `secret`, `token`, `api_key`) 的值被替换为 `[REDACTED]`
- [ ] `args_digest` 长度不超过 1024 字符

### M16.9.5 审计日志分页查询

```bash
# 分页测试
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?page=1&page_size=5" | jq '{total: .data.total, items_count: (.data.items | length), page: .data.page}'
```

Assertions:
- [ ] 返回 `total`, `items` (≤ page_size), `page`
- [ ] `items` 按 `created_at` 降序排列
- [ ] 非 owner 访问 → 403

### M16.9.6 审计日志过滤

```bash
# 按 event_type 过滤
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?event_type=tool_call&page_size=5" | jq '.data.items[].event_type' | sort -u

# 按 tool_name 过滤
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?tool_name=get_assets&page_size=5" | jq '.data.items[].tool_name' | sort -u

# 按日期范围过滤
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/access-logs?date_from=2026-01-01&date_to=2026-12-31&page_size=5" | jq '.data.total'
```

Assertions:
- [ ] `event_type` 过滤仅返回匹配类型
- [ ] `tool_name` 过滤仅返回匹配工具
- [ ] `date_from` / `date_to` 过滤正确排除范围外数据

### M16.9.7 嵌套结构递归脱敏 (P2 修复验证)

> 验证 `_redact_obj()` 对嵌套 dict/list 中的敏感值进行递归脱敏。
> 通过单元测试直接验证 (仿真环境难以构造包含嵌套密钥的工具调用)。

```bash
cd server && uv run pytest tests/backend/unit/test_mcp_audit_log.py -v -k "redact" --tb=short 2>&1 | tail -20
```

Assertions (单元测试):
- [ ] `{"config": {"api_key": "sk-xxx"}}` → `{"config": {"api_key": "[REDACTED]"}}`
- [ ] `{"nested": {"deep": {"password": "secret123"}}}` → 三层嵌套均被脱敏
- [ ] `[{"token": "mcp_xxx"}, {"key": "value"}]` → list 中的 dict 也被处理
- [ ] 深度超过 10 层时返回 `"[MAX_DEPTH]"` (防止无限递归)
- [ ] 非敏感嵌套值保持不变: `{"data": {"name": "test"}}` → 原样保留

---

## M16.10 — Per-Token 速率限制 (Phase 2, P2-R9 — P2-R10)

API: `GET /api/v1/mcp/public/{family_id}/sse`

### M16.10.1 正常速率内全部通过

```bash
# 快速发送 10 次连接 (远低于 30/min 限制)
for i in $(seq 1 10); do
  CODE=$(timeout 2 curl -sf -N \
    -H "Authorization: Bearer $MCP_TOKEN" \
    "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
    -o /dev/null -w "%{http_code}" 2>/dev/null || echo "timeout")
  echo "Request $i: $CODE"
done
```

Assertions:
- [ ] 全部 10 次返回 HTTP 200

### M16.10.2 超过 30/min → 429

```bash
# 快速发送 35 次连接
for i in $(seq 1 35); do
  CODE=$(timeout 2 curl -s -N \
    -H "Authorization: Bearer $MCP_TOKEN" \
    "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
    -o /dev/null -w "%{http_code}" 2>/dev/null || echo "timeout")
  if [ "$CODE" = "429" ]; then
    echo "Rate limited at request $i"
    break
  fi
done
```

Assertions:
- [ ] 在第 31 次左右开始返回 HTTP 429
- [ ] 429 响应包含 `RATE_LIMITED` 错误码

### M16.10.3 不同 IP 独立计数

> 无法在本地模拟不同 IP, 通过代码审查确认:
> 速率限制 key 为 `(token_prefix, client_ip)`, 不同 IP 使用独立计数器。

Assertions (代码审查):
- [ ] 速率限制 key 包含 client_ip 分量
- [ ] X-Forwarded-For 正确处理 (信任代理配置)

### M16.10.4 无效 token 不消耗速率限额

```bash
# 用无效 token 发送请求
for i in $(seq 1 5); do
  timeout 2 curl -s -N \
    -H "Authorization: Bearer mcp_invalid_xxxxxxxxxxxxx" \
    "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
    -o /dev/null 2>/dev/null || true
done

# 然后用有效 token 发送 30 次 — 应该全部通过 (无效请求不占配额)
LIMITED=0
for i in $(seq 1 30); do
  CODE=$(timeout 2 curl -s -N \
    -H "Authorization: Bearer $MCP_TOKEN" \
    "${API_BASE}/mcp/public/${FAMILY_ID}/sse" \
    -o /dev/null -w "%{http_code}" 2>/dev/null || echo "timeout")
  if [ "$CODE" = "429" ]; then
    LIMITED=$((LIMITED + 1))
  fi
done
echo "Rate limited count: $LIMITED (expected: 0)"
```

Assertions:
- [ ] 无效 token 请求后, 有效 token 的 30 次请求全部通过 (429 count = 0)

### M16.10.5 速率限制 fail-open (缓存不可用时)

> 验证当缓存后端不可用时，速率限制 fail-open（允许请求通过）而不是 fail-closed（拒绝请求）。
> 此测试需要代码审查或 mock 缓存不可用场景。

```bash
# 代码审查验证:
# 1. 检查 _check_mcp_rate_limit() 中的异常处理
grep -A 10 "def _check_mcp_rate_limit" server/apps/backend/app/routers/mcp_public.py
```

Assertions (代码审查):
- [ ] 缓存异常被 `except Exception` 捕获
- [ ] 异常时仅记录 WARNING 日志，不抛出 AppError
- [ ] 请求在缓存不可用时仍能通过（fail-open）
- [ ] `except AppError: raise` 确保 429 不被吞掉

---

## M16.11 — 异常检测与通知 (Phase 2, P2-R11 — P2-R13)

Scheduler: `mcp_anomaly_scan_job` (every 5 min)
Notification: `mcp_security` / `mcp_anomaly_detected`

### M16.11.1 频率突增告警

> 需要 seed 数据或使用测试环境触发。

```bash
# 通过单元测试验证 (非仿真测试范围, 此处记录验证命令)
cd server && uv run pytest tests/backend/services/test_mcp_anomaly.py -v -k frequency
```

Assertions:
- [ ] 5 分钟内 >100 次工具调用 → 产生 `mcp_anomaly_detected` Reminder
- [ ] Reminder 包含异常类型描述和摘要

### M16.11.2 新来源 IP 告警 (P2-R11b)

> 30 天窗口内首次出现的来源 IP 触发告警。
> **基线前提:** 仅当 family 已存在历史审计记录时才检测 — 否则首个连接会被误判为"新 IP"。

```bash
cd server && uv run pytest tests/backend/services/test_mcp_anomaly.py -v -k "NewSourceIP" --tb=short
```

Assertions:
- [ ] `test_new_ip_emits_alert`: 已知 IP (10 天前) + 新 IP (1 分钟前) → 产生 `new_source_ip` 告警
- [ ] `test_known_ip_no_alert`: 同一 IP 在历史窗口内出现过 → 不告警
- [ ] `test_ip_outside_lookback_window_is_new`: IP 最后出现于 45 天前 (超出 30 天窗口) → 视为新 IP
- [ ] `test_unknown_ip_sentinel_ignored`: `client_ip == "unknown"` 哨兵值不触发告警
- [ ] `test_new_ip_dedup_within_hour`: 连续扫描仅产生 1 个告警
- [ ] `test_first_ever_connection_no_alert`: family 无历史记录时不告警 (基线缺失)
- [ ] 配置项: `MCP_ANOMALY_NEW_IP_WINDOW_MINUTES` (默认 5), `MCP_ANOMALY_NEW_IP_HISTORY_DAYS` (默认 30)

> **去重语义:** 每个条件（不同 `anomaly_type` / 不同 IP）拥有独立的告警身份，
> 互不抑制。同一条件 1 小时内只告警一次。见 M16.11.4。

### M16.11.3 高失败率告警

```bash
cd server && uv run pytest tests/backend/services/test_mcp_anomaly.py -v -k failure_rate
```

Assertions:
- [ ] 10 分钟内 >50% 失败 (至少 5 次调用) → 产生告警

### M16.11.4 告警去重 (按条件, 1 小时窗口)

> 去重键为 `(family_id, reminder_type, title)`，其中 title 是**条件标识**
> （如 `MCP 异常 [new_source_ip]: 新来源 IP 1.2.3.4`）。
> 度量值（调用次数、失败率）放在 body，不参与去重 —— 否则每次扫描都会新建告警。
> `ensure_reminder(dedup_by_title=True)` 使不同条件可各自保留一条未处理提醒。

```bash
cd server && uv run pytest tests/backend/services/test_mcp_anomaly.py -v -k "dedup or drift or distinct or same_ip" --tb=short
```

Assertions:
- [ ] 同一条件 1 小时内仅产生 1 个 Reminder (`test_dedup_within_one_hour`)
- [ ] 不同条件各自告警，即使前一条仍未处理 (`test_two_distinct_new_ips_each_alert`)
- [ ] 同一 IP 重复扫描不产生新 Reminder (`test_same_ip_does_not_duplicate_across_scans`)
- [ ] 度量值漂移不破坏去重 (`test_drift_in_measurement_does_not_defeat_dedup`)
- [ ] `ensure_reminder` 默认行为不变（其他 reminder_type 仍按 type 幂等，61 个通知测试通过）

### M16.11.5 通知注册表包含 mcp_security 类别

```bash
# 检查通知设置页面是否有 MCP 安全类别
```

```
bsk navigate ${BASE}settings/notifications --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.11.5-notification-settings.png
```

Assertions:
- [ ] 通知设置页包含 "MCP 安全" / "MCP Security" 分类
- [ ] 该分类下有 "MCP 异常调用" / "MCP Anomaly Detected" 事件类型可订阅
- [ ] i18n key 正确 (中英文均渲染正常)
- [ ] `[console]` zero errors

### M16.11.6 ReminderSummary 包含 mcp_anomaly_detected 计数

```bash
# 通过 /notifications/summary API 验证
curl -s -H "$AUTH" "${API_BASE}/notifications/summary" | jq '.data.mcp_anomaly_detected // 0'
```

Assertions:
- [ ] `ReminderSummary` 包含 `mcp_anomaly_detected` 字段
- [ ] 无告警时值为 0

### M16.11.7 动态 count 不影响去重 (P3 修复验证)

> 修复前: 告警 title 包含动态 count (如 "5 分钟内 120 次工具调用"),
> 导致每次扫描 count 变化时 dedup 失效, 持续产生重复告警。
> 修复后: dedup key 使用稳定的 `anomaly_type`, 动态数字仅在显示 title 中。

```bash
# 通过单元测试验证
cd server && uv run pytest tests/backend/services/test_mcp_anomaly.py -v -k dedup --tb=short 2>&1 | tail -15
```

Assertions (单元测试):
- [ ] `test_dedup_within_one_hour` 测试通过: 连续两次扫描 (相同 count) 仅产生 1 个 Reminder
- [ ] 代码审查: `_emit_anomaly_alert()` 使用 `stable_dedup_title = f"MCP 异常: {anomaly_type}"`
  而非动态 title 作为 dedup key
- [ ] 用户可见的 `Reminder.title` 仍包含动态 count (用于展示), 但 dedup 基于稳定 key
- [ ] 不同 `anomaly_type` (frequency_spike vs high_failure_rate) 独立去重

---

## M16.12 — 统计面板 (Phase 2, P2-R14 — P2-R17)

Route: `/settings/ai/mcp/stats`
API: `GET /api/v1/ai/mcp-token/stats`
Component: `MCPStatsPage.vue`

### M16.12.1 卡片摘要行

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.12.1-mcp-card-summary.png
```

Assertions:
- [ ] 卡片底部显示使用摘要行: 今日调用数 + 成功率
- [ ] 如果有异常 (24h 内), 显示警告图标
- [ ] 点击摘要行可导航到统计页

### M16.12.2 Stats API 返回聚合数据

```bash
STATS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/stats")
echo "$STATS" | jq '.data | {total_calls, success_count, failure_count, success_rate}'
```

Assertions:
- [ ] 返回 `total_calls`, `success_count`, `failure_count`, `error_count`, `permission_denied_count`
- [ ] `success_rate` 为 0-1 之间的浮点数
- [ ] 包含 `hourly_buckets` 数组
- [ ] 包含 `tool_breakdown` 数组
- [ ] 包含 `ip_breakdown` 数组
- [ ] 默认范围为最近 7 天

### M16.12.3 Stats API 日期范围过滤

```bash
# 自定义日期范围
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/stats?from=2026-10-01&to=2026-10-10" | jq '.data.total_calls'

# 仅今天
TODAY=$(date +%Y-%m-%d)
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/stats?from=${TODAY}" | jq '.data.total_calls'
```

Assertions:
- [ ] 日期范围过滤正确影响聚合结果
- [ ] `from` 和 `to` 参数可选

### M16.12.4 统计页面渲染

```
bsk navigate ${BASE}settings/ai/mcp/stats --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/m16.12.4-stats-page.png
```

Assertions:
- [ ] PageHeader 显示 "MCP 使用统计"
- [ ] 日期范围选择器可用 (最近 7 天 / 30 天 / 自定义)
- [ ] 调用趋势折线图渲染 (或空态 "暂无数据")
- [ ] 工具分布柱状图渲染 (或空态)
- [ ] Top 源 IP 列表渲染 (或空态)
- [ ] 失败率趋势折线图渲染 (或空态)
- [ ] `[console]` zero errors

### M16.12.5 统计页面日期切换

```
bsk snapshot --session <id>
# 切换到 "30 天"
bsk click @eN --session <id>   # date range picker
bsk snapshot --session <id>
# 选择 30 天
bsk click @eN --session <id>   # "30 days" option
bsk snapshot --session <id>
```

Assertions:
- [ ] API 以新日期范围重新请求
- [ ] 图表重新渲染
- [ ] `[console]` zero errors

### M16.12.6 空数据状态

```bash
# 对无审计数据的 family 查询
# (如果是新 family 或无外部调用)
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/stats" | jq '.data.total_calls'
```

```
bsk navigate ${BASE}settings/ai/mcp/stats --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `total_calls == 0`
- [ ] 四个图表均显示 "暂无数据" 空态
- [ ] 无渲染错误
- [ ] `[console]` zero errors

### M16.12.7 非 owner 无法访问统计页

```
# 使用 member 角色账户 (deferred — 需要 member 账户)
# bsk navigate ${BASE}settings/ai/mcp/stats --session <member_id>
```

Assertions:
- [ ] 非 owner 访问统计页 → 重定向到 `/settings/ai/mcp` + toast 提示
- [ ] 非 owner 卡片摘要行只读 (不可点击导航)

### M16.12.8 非 owner GET /stats → 403

```bash
# 使用 member token (deferred)
# curl -s -H "$MEMBER_AUTH" "${API_BASE}/ai/mcp-token/stats" | jq '.code'
```

Assertions:
- [ ] HTTP 403 (require_owner 守卫)

---

## M16.13 — 工具目录 API (Phase 2, P2-R3 UI side)

API: `GET /api/v1/ai/mcp-token/tools`

### M16.13.1 工具目录返回完整列表

```bash
TOOLS=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token/tools")
echo "$TOOLS" | jq '.data.tools | length'
echo "$TOOLS" | jq '.data.tools[] | {name, requires_write}'
```

Assertions:
- [ ] 返回 16 个工具 (12 读 + 4 写)
- [ ] 每个工具包含 `name`, `description`, `requires_write`
- [ ] 读工具 `requires_write == false`
- [ ] 写工具 `requires_write == true`

---

## M16.14 — GET /ai/mcp-token 元数据只读安全 (Phase 1, R14)

API: `GET /api/v1/ai/mcp-token`

### M16.14.1 GET 不返回 hash 或明文

```bash
RESP=$(curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token")
echo "$RESP" | jq '.data'
```

Assertions:
- [ ] 响应包含: `token_prefix`, `token_last4`, `allow_external`, `allow_write`, `expires_at`, `last_used_at`, `is_active`, `created_at`
- [ ] 响应 **不包含** `token_hash` 字段
- [ ] 响应 **不包含** `token` (明文) 字段
- [ ] `token_prefix` 为 8 字符
- [ ] `token_last4` 为 4 字符

### M16.14.2 无 token 时 GET → 404

```bash
# 先删除 token
curl -s -H "$AUTH" -X DELETE "${API_BASE}/ai/mcp-token"
# GET 应返回 404
curl -s -H "$AUTH" "${API_BASE}/ai/mcp-token" -w "\n%{http_code}" | tail -1
```

Assertions:
- [ ] HTTP 404

---

## M16.15 — 权限边界 (Phase 1 & 2, R10, R20)

### M16.15.1 非 owner (adult member) 查看 token 状态 (只读)

> Deferred: 需要 member 角色账户。

Assertions:
- [ ] 非 owner 可在卡片看到掩码 token、开关状态 (只读)
- [ ] 开关和按钮 disabled
- [ ] 无 "生成令牌" / "重新生成" 按钮

### M16.15.2 非 owner 调用管理 API → 403

```bash
# 以下 API 全部需要 owner 权限
# POST (generate)
curl -s -H "$MEMBER_AUTH" -X POST "${API_BASE}/ai/mcp-token" | jq '.code'
# PATCH (update)
curl -s -H "$MEMBER_AUTH" -X PATCH "${API_BASE}/ai/mcp-token" \
  -H 'Content-Type: application/json' \
  -d '{"allow_external": true}' | jq '.code'
# DELETE (revoke)
curl -s -H "$MEMBER_AUTH" -X DELETE "${API_BASE}/ai/mcp-token" | jq '.code'
# GET /access-logs
curl -s -H "$MEMBER_AUTH" "${API_BASE}/ai/mcp-token/access-logs" | jq '.code'
# GET /stats
curl -s -H "$MEMBER_AUTH" "${API_BASE}/ai/mcp-token/stats" | jq '.code'
```

Assertions:
- [ ] 所有管理端点返回 HTTP 403
- [ ] 错误码为 `FORBIDDEN` 或 `REQUIRE_OWNER`

---

## 测试后清理

```bash
# 清理: 撤销 MCP token
curl -s -H "$AUTH" -X DELETE "${API_BASE}/ai/mcp-token" > /dev/null 2>&1
unset MCP_TOKEN OLD_TOKEN FAMILY_ID
```

---

## 用例摘要

| Case | 标题 | 类型 | 覆盖需求 |
|------|------|------|----------|
| M16.1.1 | 无 token 时卡片初始状态 | UI | R15, R16 |
| M16.1.2 | 首次生成 token | UI | R2, R11, R16 |
| M16.1.3 | API 验证: 生成返回明文 | API | R1, R2, R11 |
| M16.2.1 | Token 掩码显示 | UI | R16 |
| M16.2.2 | 眼睛切换 + 10s 自动遮罩 | UI | R16 |
| M16.2.3 | 复制到剪贴板 | UI | R16 |
| M16.2.4 | 过期时间选择器 | UI | R18 |
| M16.3.1 | Bearer token 认证连接 | API | R7, R9 |
| M16.3.2 | 无效 token → 401 | API | R9 |
| M16.3.3 | allow_external=False → 403 | API | R5, R9 |
| M16.3.4 | 过期 token → 401 | API | R9 |
| M16.3.5 | Query param 认证 + 审计 WARNING | API | R6, R7 |
| M16.3.6 | 已撤销 token → 401 | API | R3, R9 |
| M16.3.7 | User-Agent 控制字符清洗 | API | P3-sec |
| M16.4.1 | 仅读工具 (allow_write=False) | API | R5 |
| M16.4.2 | 包含写工具 (allow_write=True) | API | R5, R12 |
| M16.4.3 | allow_external 开关确认对话框 | UI | R17 |
| M16.4.4 | allow_write 开关确认对话框 | UI | R17 |
| M16.5.1 | 合成用户不在成员列表 | API | R4 |
| M16.5.2 | 合成用户无法登录 | API | R4 |
| M16.5.3 | 合成用户 role 字段长度 | API | bug-fix |
| M16.6.1 | 内部 agent 路径不受影响 | API | R21 |
| M16.6.2 | bootstrap 系统 MCP server 不变 | API | R22 |
| M16.7.1 | 前端轮转确认对话框 | UI | R3, R16 |
| M16.7.2 | 撤销 token (DELETE) | API | R13 |
| M16.7.3 | 撤销后前端状态 | UI | R13, R15 |
| M16.8.1 | 默认 allowed_tools=null | API | P2-R1 |
| M16.8.2 | 工具权限弹窗 — 全选状态 | UI | P2-R3 |
| M16.8.3 | 取消勾选一个工具并保存 | UI | P2-R3 |
| M16.8.4 | 无效工具名 → 400 | API | P2-R3 |
| M16.8.5 | allowed_tools=null 重置 | API | P2-R3 |
| M16.8.6 | allowed_tools=[] 无工具 | API | P2-R3 |
| M16.8.7 | "全部启用" → PATCH null | UI | P2-R3 |
| M16.8.8 | 隐藏写工具不被保存到后端 | UI | P1-fix |
| M16.9.1 | connect 事件审计 | API | P2-R4, P2-R6 |
| M16.9.2 | tool_call 事件审计 | API | P2-R4, P2-R6 |
| M16.9.3 | 内部路径无审计行 | API | P2-R5, P2-AE10 |
| M16.9.4 | args_digest 密钥脱敏 | API | P2-R4 |
| M16.9.5 | 审计日志分页 | API | P2-R8 |
| M16.9.6 | 审计日志过滤 | API | P2-R8 |
| M16.9.7 | 嵌套结构递归脱敏 | Unit | P2-fix |
| M16.10.1 | 正常速率全部通过 | API | P2-R9 |
| M16.10.2 | 超过 30/min → 429 | API | P2-R9 |
| M16.10.3 | 不同 IP 独立计数 | Review | P2-R9 |
| M16.10.4 | 无效 token 不消耗配额 | API | P2-R10 |
| M16.10.5 | 速率限制 fail-open | Review | P1-fix |
| M16.11.1 | 频率突增告警 | Unit | P2-R11 |
| M16.11.2 | 新来源 IP 告警 | Unit | P2-R11b |
| M16.11.3 | 高失败率告警 | Unit | P2-R11 |
| M16.11.4 | 告警去重 | Unit | P2-R13 |
| M16.11.5 | 通知注册表 mcp_security | UI | P2-R12 |
| M16.11.6 | ReminderSummary 计数 | API | P2-R12 |
| M16.11.7 | 动态 count 不影响去重 | Unit | P3-fix |
| M16.12.1 | 卡片摘要行 | UI | P2-R14 |
| M16.12.2 | Stats API 聚合数据 | API | P2-R15 |
| M16.12.3 | Stats API 日期范围 | API | P2-R15 |
| M16.12.4 | 统计页面渲染 | UI | P2-R16 |
| M16.12.5 | 统计页面日期切换 | UI | P2-R16 |
| M16.12.6 | 空数据状态 | UI | P2-R16 |
| M16.12.7 | 非 owner 无法访问统计页 | UI | P2-R17 |
| M16.12.8 | 非 owner GET /stats → 403 | API | P2-R17 |
| M16.13.1 | 工具目录完整列表 | API | P2-R3 |
| M16.14.1 | GET 不返回 hash 或明文 | API | R14 |
| M16.14.2 | 无 token 时 GET → 404 | API | R14 |
| M16.15.1 | 非 owner 只读查看 | UI | R20 |
| M16.15.2 | 非 owner API → 403 | API | R10 |

**Total: 66 cases** (21 UI + 37 API + 6 Unit + 2 Code Review)

### 修复验证覆盖 (Review-Fix Regression)

| Case | 验证的修复 | 严重度 |
|------|-----------|--------|
| M16.3.7 | User-Agent 控制字符清洗 | P3 |
| M16.5.3 | `users.role` VARCHAR(20) 扩展 | 仿真 bug |
| M16.8.8 | 工具选择器隐藏工具过滤 | P1 |
| M16.9.7 | 嵌套结构递归脱敏 | P2 |
| M16.10.5 | 速率限制 fail-open | P1 |
| M16.11.7 | 动态 count 不影响去重 | P3 |

> 其余修复项通过既有用例间接覆盖:
> - **P0 dialect-aware 日期格式化**: M16.12.2 (Stats API 在 PostgreSQL 上运行)
> - **P1 timing-safe hash**: M16.3.x (认证行为正确性)
> - **P2 per-alert commit**: M16.11.1-3 (告警产生正确性)

### 需求补齐记录

经测试用例审查发现并补齐的两项:

**1. P2-R11(b) 新来源 IP 告警** — 初版实现遗漏该阈值 (仅实现频率突增与高失败率)。

- 实现: `mcp_anomaly.py` Threshold 3，`new_source_ip` 告警类型
- 配置: `MCP_ANOMALY_NEW_IP_WINDOW_MINUTES` (默认 5) / `MCP_ANOMALY_NEW_IP_HISTORY_DAYS` (默认 30)
- 基线语义: family 无历史记录时不告警 (首个连接无参照基线，否则必然误报)
- 覆盖: M16.11.2 (7 个单元测试)

**2. P2-R13 按条件去重** — 初版实际被 `ensure_reminder` 的
`(family_id, reminder_type, asset_id, active)` 幂等键覆盖，导致每个家庭同时只能存在
一条未处理的 MCP 异常提醒：前一条未处理期间，其他类型/其他 IP 的异常被静默抑制。

- 修复: `ensure_reminder(..., dedup_by_title=True)` 选择性让 title 参与幂等判断（opt-in，其他调用方行为不变）
- 标题改为条件标识（IP / 固定短语），度量值移入 body
- 覆盖: M16.11.4 (4 个单元测试 + 61 个通知测试回归)

---
