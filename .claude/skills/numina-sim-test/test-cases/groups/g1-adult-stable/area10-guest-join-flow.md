# Area 10 — Guest 端到端注册 + 加入家庭

Shared conventions in [`_common.md`](../../_common.md).

> **与 F.5 的差异:** F.5 验证 Guest 页面 *渲染* (welcome / register /
> join-family / promo 各页面加载正常)。Area 10 验证 *端到端提交流程*
> — 从填写表单到账户创建 / 加入家庭成功。需要 fresh bsk session (无 cookie)。

> **Reverse-engineered from** backend `test_auth.py` (registration flow +
> duplicate handling), `test_family_invitation_code.py` (code generation +
> validation + reuse limit), `test_family.py` (family creation + join
> family member addition). 前端 `RegisterPage.vue` + `JoinFamilyPage.vue`
> 表单校验。

## 前置

```bash
# 1. 停止当前 adult session (cookie 会污染 guest 流程)
bsk session stop "$SID"

# 2. 启动 fresh session (无 cookie, 无 localStorage)
SID_GUEST=$(bsk session start --json | jq -r .session_id)

# 3. 可选: 生成邀请码 (通过 API, 用 demouser 账户)
INVITE_CODE=$(curl -s -H "Authorization: Bearer $TOKEN" \
  -X POST "${API_BASE}/family/invitation-code" | jq -r '.data.code')
echo "Invite code: $INVITE_CODE"
```

### C10.1 Register — 新用户注册成功

```
bsk navigate "${BASE}register" --session "$SID_GUEST" --wait-until networkidle
bsk snapshot --session "$SID_GUEST"
```

Assertions:
- [ ] 注册表单字段: username / display_name / password / confirm_password
- [ ] 空字段提交 → 各字段下方显示校验错误 (红色文字)
- [ ] 密码弱 (如 "123") → 密码强度提示 / 校验拒绝
- [ ] 两次密码不一致 → "密码不一致" 错误
- [ ] 重复 username → 服务端返回错误, 表单显示 "用户名已存在"
- [ ] 填写合法数据 → 提交 → 自动登录 + 跳转 dashboard
- [ ] 新建账户自动创建家庭 (role=owner), /auth/me 返回 family_id
- [ ] `[console]` zero errors

> **测试后清理:** 通过 API 删除刚创建的测试用户, 避免污染后续注册测试:
> ```bash
> curl -X DELETE "${API_BASE}/auth/me" -H "Authorization: Bearer $NEW_TOKEN"
> ```
> 或在报告中标注测试用户名 (如 `testreg_YYYYMMDD`) 方便后续清理。

### C10.2 Join Family — 邀请码加入家庭

```
# 先用 C10.1 创建新账户 (或用已存在的测试账户), 登录获取 token
# 确保 demouser 已生成邀请码 (INVITE_CODE 变量)

bsk navigate "${BASE}join-family" --session "$SID_GUEST" --wait-until networkidle
bsk snapshot --session "$SID_GUEST"
```

Assertions:
- [ ] 表单有邀请码输入框
- [ ] 空码提交 → "请输入邀请码" 校验错误
- [ ] 无效码 (如 "INVALID") → "邀请码无效或已过期" 错误
- [ ] 过期码 → 同上错误 (后端 `invitation_code.expires_at` 校验)
- [ ] 有效码 → 提交 → 跳转 dashboard, 身份变为 member (非 owner)
- [ ] `/auth/me` 返回 `family_id` = demouser 的 family_id, `role` = "member"
- [ ] 新成员可见 demouser 家庭的资产/负债/心愿 (只读 member 权限)
- [ ] `[console]` zero errors

> **测试后清理:** 用 demouser (owner) 把新成员从家庭移除:
> ```bash
> curl -X DELETE "${API_BASE}/family/members/<new_member_id>" \
>   -H "Authorization: Bearer $DEMOUSER_TOKEN"
> ```

### C10.3 邀请码复用上限 + 重新生成

```
# 使用 demouser 的 owner 权限测试邀请码管理
# 需要先恢复 adult session
bsk session stop "$SID_GUEST"
SID=$(bsk session start --json | jq -r .session_id)
# 通过 Phase 2 cookie injection 恢复 demouser session
```

Assertions:
- [ ] `/family/invitation-code` GET 返回当前码 + 过期时间
- [ ] "重新生成" 按钮 → 旧码失效, 新码生成
- [ ] 旧码不能再用于 join-family (C10.2 的 "无效码" 分支验证)
- [ ] 邀请码使用次数达到上限 (default=1?) 后 → 新注册用该码被拒
- [ ] `[console]` zero errors

### C10.4 Register + Join Family — 已登录用户访问 Guest 页面

```
# 已登录 demouser, 访问 /register 或 /join-family
bsk navigate "${BASE}register" --session "$SID" --wait-until networkidle
bsk snapshot --session "$SID"
```

Assertions:
- [ ] 路由守卫检测到已登录 → 重定向到 dashboard (不是渲染注册表单)
- [ ] `/join-family` 同样被重定向
- [ ] 重定向后 Dashboard 正常渲染
- [ ] `[console]` zero errors

## 清理

```bash
bsk session stop "$SID_GUEST"
# 恢复 adult session 给后续 Phase 使用
SID=$(bsk session start --json | jq -r .session_id)
# Phase 2 cookie injection 恢复 demouser
```
