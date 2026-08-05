# Area 9 — Account security + notification (账户安全 + 通知)

Shared conventions in [`_common.md`](../../_common.md).

Auth: adult session as `demouser` / `DemoPass123` (SKILL.md Phase 2
cookie+localStorage fallback preferred). All routes under `${BASE}`.

> **Reverse-engineered from** the backend `test_webauthn.py`,
> `test_device_webauthn.py`, `test_device_auth.py`, `test_device_multi_account.py`,
> `test_notification_channels.py`, `test_notification_rules.py`, `test_reminders.py`,
> plus the main-frontend `useMemberNotify.spec.ts` + Settings page rendering
> paths. These features have extensive backend + composable unit coverage but
> no end-to-end UI sim-test. Fills the HIGH/MEDIUM gaps in the previous
> sim-test inventory.

### C9.1 WebAuthn 注册 / 登录流程

```
bsk navigate ${BASE}settings/security --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] "注册安全密钥" 按钮可见 + 可点击
- [ ] 点击后浏览器弹出 WebAuthn 原生对话框 (bsk 不驱动原生弹窗 — 截图记录弹窗出现)
- [ ] 注册成功后列表中出现新密钥条目 (名称 + 注册日期 + "最近使用")
- [ ] 已注册密钥出现在列表 → 登录页可见 "使用安全密钥" 选项
- [ ] 删除密钥 → 确认对话框 → 列表刷新
- [ ] `[console]` zero errors (WebAuthn 不支持降级错误)

> **bsk 限制:** WebAuthn 原生对话框无法由 bsk 驱动。用例验证 UI 路径 +
> 列表状态; 实际密钥注册需用户在真实浏览器手动完成。

### C9.2 2FA 启用 / 禁用 / 验证码

```
bsk navigate ${BASE}settings/security --session <id> --wait-until networkidle
bsk click @eN --session <id>   # "启用两步验证"
```

Assertions:
- [ ] 弹出 QR 码对话框, 含 secret 文本 + 二维码
- [ ] 输入框接受 6 位 TOTP 码
- [ ] 错误码 → 抖动 + 错误提示 ("验证码无效, 请重试")
- [ ] 正确码 (从 authenticator app 取) → 2FA 启用, 显示恢复码 (一次性展示)
- [ ] 恢复码复制按钮可点, 复制到剪贴板
- [ ] 禁用 2FA → 要求输入当前密码 → 成功后按钮回到 "启用"
- [ ] `[console]` zero errors

> **测试数据:** `demouser` 账户默认未启用 2FA。测试前先确保未启用;
> 测试结束后禁用, 留给下一个用例干净状态。

### C9.3 设备管理页 — 多设备列表 + 强制登出

```
bsk navigate ${BASE}settings/devices --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 当前设备行带 "此设备" 标签
- [ ] 显示设备名 + 浏览器 + 最后登录时间
- [ ] "强制登出" 按钮对当前设备禁用 (不能登出自己)
- [ ] 其他设备的 "强制登出" 可点 → 确认对话框 → 设备从列表移除
- [ ] 被登出设备的 cookie 失效 (下次访问跳 /login)
- [ ] `[console]` zero errors

> **前置:** 测试需要 ≥2 个登录设备。如果只有 1 个, 用另一浏览器
> (如 Firefox) 登录 demouser 制造第二条设备记录; 或在报告中标注 SKIP
> ("单设备环境, 无法测试强制登出")。

### C9.4 通知规则触发 — toast 实际弹出

```
# 先在 /settings/notifications 配置一条规则 (如 负债到期前 3 天提醒)
bsk navigate ${BASE}settings/notifications --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 启用 "负债提醒" 通道, 设置阈值 = 3 天
```

Assertions:
- [ ] 规则保存 → 成功 toast 出现
- [ ] 通知规则列表显示: 通道 + 阈值 + 启用状态
- [ ] 切换开关 → 立即生效 (API PUT 200, 无需 reload)
- [ ] 触发条件存在时 (负债 3 天内到期), Dashboard 顶部出现通知横幅
- [ ] 点击通知横幅 → 跳转到负债详情页 (`/liabilities/<id>`)
- [ ] `[console]` zero errors

> **触发前置:** 需要一条 3 天内到期的负债。如果 demouser 没有, 通过
> API 临时创建 (`POST /liabilities` + 下次付款日期 = 明天), 测试后删除。
> 或在报告中标注 SKIP-NO-DATA。

### C9.5 AI 模型测试按钮 — 连通性验证

```
bsk navigate ${BASE}settings/ai/provider/<current> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 找到 "测试模型" / "Test connection" 按钮
```

Assertions:
- [ ] 按钮存在 + 可点击
- [ ] 点击后按钮进入 loading 状态 (禁用 + spinner)
- [ ] 成功: 绿色 toast "模型连接成功" + 显示响应时间
- [ ] 失败: 红色 toast 显示错误 (如 "API key 无效" / "模型不存在" / "超时")
- [ ] 失败时不跳转页面, 用户留在当前表单
- [ ] `[console]` zero errors

> **AI 必须启用:** 如果 family aiEnabled=false, 跳过并标注 SKIP-AI。

### C9.6 通知中心 — 已读 / 未读 / 清空

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 找到顶部通知铃铛图标 (带未读数 badge)
```

Assertions:
- [ ] 铃铛图标显示未读数 badge (如有)
- [ ] 点击铃铛 → 下拉通知列表 (或跳转到通知页)
- [ ] 未读条目有视觉区分 (粗体 / 背景色 / 圆点)
- [ ] 点击单条 → 标记已读 + 跳转到相关页面
- [ ] "全部已读" 按钮 → 所有条目变为已读样式, badge 清零
- [ ] "清空" 按钮 → 列表清空 (带确认对话框)
- [ ] `[console]` zero errors

### C9.7 会话超时 + 重新登录 — 数据保留

```
# 模拟 session 过期 (手动清 localStorage, 类似 R6)
bsk evaluate --session <id> "localStorage.clear()"
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 应被路由守卫重定向到 /login
```

Assertions:
- [ ] 路由守卫检测到未登录 → 重定向到 `/login`
- [ ] 重新登录后 → 回到原路由 (dashboard), 不是永远停在 /login
- [ ] 重新登录后, `demouser` 的 localStorage `numina_user` 重新填充
- [ ] 如果之前有进行中的 AI chat → 重新登录后 chat 历史仍在 (服务端持久化)
- [ ] `[console]` zero errors

> **与 R6 的差异:** R6 验证的是 session 过期后 *立即* 重定向。C9.7 验证
> 重新登录后 *数据保留* 和 *chat 历史延续* — 端到端恢复流。
