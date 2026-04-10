---
date: 2026-04-10
topic: ai-health-report
---

# 家庭资产体检报告

## Problem Frame

家庭成员在 Numina 中积累了资产、负债、快照等大量数据，但缺乏一个"解读层"——用户需要自己在多个 Dashboard 面板之间切换、心算比率、判断风险，认知负担高。体检报告将这些分散信号综合为一份带叙事的结构化健康评估，让家庭管理员和成员无需财务专业知识也能理解家庭资产的整体状况和需要关注的问题。

这是 AI 模块的**旗舰功能**，也是验证 AI 基础设施（管理员开关、脱敏管道、LLM 封装）可行性的第一个落地场景。

```
用户进入报告页
      │
      ▼
  有缓存报告？ ──是──▶ 展示最新报告（显示生成时间）
      │                        │
      否                  用户点击"刷新"
      │                        │
      ▼                        ▼
  触发生成 ◀──────────────────────
      │
      ▼
  聚合 Dashboard 数据
      │
      ▼
  脱敏处理（剥离姓名/账号，保留精确金额+类别）
      │
      ▼
  调用 LLM 生成叙事
      │
      ▼
  存储报告（保留最近6份）
      │
      ▼
  返回结构化报告 JSON
      │
      ▼
  H5 卡片组渲染
```

---

## Requirements

**AI 基础设施前提（Phase 0，本功能依赖）**

- R0. 独立 `agent/` Python 模块，与 `backend/app/` 并列，包含 LLM 调用封装、脱敏管道、AI 配置管理。
- R1. `Family` 模型新增 `ai_enabled: bool`（默认 `False`）和 `ai_provider: str | None`、`ai_api_key_encrypted: str | None` 字段。
- R2. 仅家庭管理员（`role == 'owner'`）可通过 `PUT /api/v1/ai/config` 配置 AI 开关和 provider 信息。
- R3. 所有 `/api/v1/ai/` 端点在 `ai_enabled == False` 时返回 `403`，响应体包含机器可读字段 `{"code": "ai_disabled", "detail": "..."}` 以便前端区分"AI未开启"（展示配置引导）与"无权限"（`code: "ai_not_authorized"`，展示"请联系管理员"）两种场景。
- R4. 脱敏管道：发送给 LLM 的数据保留精确金额和资产类别，但剥离成员姓名、资产名称（替换为类别标签）、账号信息。
- R5. 所有 AI 端点受全局限速中间件覆盖；LLM 调用额外设置 per-family 限速（每小时最多 10 次生成请求）。
- R6. AI 操作（报告生成、配置变更）通过现有 `security_log` 服务（`backend/app/services/security_log.py`）记录结构化审计事件，格式遵循已有的 `[event_type] key=value` 模式。

**报告生成**

- R7. `GET /api/v1/ai/report` 返回当前家庭最新一份报告；若无报告则返回 `404`。
- R8. `POST /api/v1/ai/report/generate` 触发按需生成；生成期间通过 WebSocket `WS /api/v1/ai/report/ws/{family_id}` 推送进度事件（`generating` → `completed` / `failed`），前端收到 `completed` 事件后自动刷新报告内容。
- R9. APScheduler 每月 1 日 08:00 Asia/Shanghai（随机偏移 0-30 分钟）自动为所有 `ai_enabled == True` 的家庭生成报告，写入 `ai_reports` 表。
- R10. 报告生成聚合以下数据源：overview（净资产/总资产/总负债）、allocation（资产配置分布）、trend（近12个月净资产趋势）、daily-cost-ranking（日均成本最高的5项资产）、low-usage（闲置资产列表）、returns（金融资产回报率）。
- R11. 每个家庭最多保留最近 6 份报告；第 7 份写入成功后原子性删除最旧一份（先写后删，避免写入失败导致报告丢失）。
- R12. 报告生成失败（LLM 超时、API 错误）时记录错误日志，不影响应用其他功能；前端展示友好错误提示。

**报告内容结构**

- R13. 报告包含以下固定模块，每个模块有标题、评分（1-5星）、AI 叙事文本（中文）、关键数据摘要：
  - **净资产健康度**：净资产绝对值、近12个月趋势方向、同比变化率
  - **资产配置分析**：实物/金融资产比例、集中度风险（单类别占比 > 50% 时预警）
  - **负债压力评估**：负债率（总负债/总资产）、月供压力比（月供合计/估算月收入）；当总资产为零时，该子指标显示"数据不足"并计为中性分
  - **资产效率分析**：闲置资产数量和占比、日均成本最高资产 Top 3
  - **综合健康评分**：基于以上4个模块加权的总分（1-100分）+ 一句话总结
- R14. 报告 JSON 结构稳定，前端按固定字段渲染，不依赖 LLM 输出格式（LLM 只生成叙事文本字段，结构化数据由后端计算填充）。
- R15. 报告包含 `generated_at` 时间戳、`data_completeness_score`（0-100）；计算方式：检查以下6个关键字段在全部资产中的填写率并取平均——`current_value`（权重30）、`purchase_price`（权重20）、`category_id`（权重20）、`expected_lifespan_days`（权重10）、`usage_frequency`（权重10）、`annual_maintenance_cost`（权重10）；当完整度低于 60 时，报告顶部展示数据质量提示。

**H5 展示**

- R16. 新增独立页面 `AIReportPage.vue`，从 `SettingsPage.vue` 或 Dashboard 顶部入口跳转进入。
- R17. 报告页顶部展示综合健康评分（大字号数字 + 颜色编码：≥80绿、60-79黄、<60红）+ 生成时间。
- R18. 各模块以 Vant `Card` 卡片组形式垂直滚动展示，每张卡片包含模块标题、星级评分、AI 叙事段落、关键数据 Tag 组。
- R19. 页面顶部固定"刷新报告"按钮；生成中时按钮显示加载状态，禁止重复触发；生成完成后自动刷新页面内容。
- R20. 支持历史报告切换：页面底部展示最近6份报告的时间选择器，用户可查看历史报告对比。
- R21. 当 `ai_enabled == False` 时，报告页展示引导卡片，提示管理员前往设置开启 AI 功能；非管理员成员看到"功能未开启，请联系家庭管理员"。
- R22. 报告页支持长截图分享，使用 `html2canvas` 库将报告卡片渲染为图片后触发系统分享或保存；截图时隐藏"刷新"按钮和导航栏。此功能依赖浏览器支持，降级时提示用户手动截图。

**AI 配置管理页**

- R23. `SettingsPage.vue` 新增"AI 智能功能"入口，仅管理员可见。
- R24. AI 配置页展示：AI 开关（Toggle）、AI Provider 选择（Anthropic Claude / OpenAI）、API Key 输入框（输入后加密存储，展示时脱敏为 `sk-****xxxx`）、连接测试按钮。
- R25. API Key 在数据库中加密存储（AES-256），不以明文出现在任何日志或响应中。

---

## Success Criteria

- 家庭管理员能在 3 步内完成 AI 功能配置（开启开关 → 选择 Provider → 输入 API Key）。
- 报告生成端到端时间（从点击到展示）< 15 秒（P90）。
- 报告内容覆盖 5 个固定模块，每个模块有可读的中文叙事，不出现乱码或空白。
- 发送给 LLM 的 payload 中不包含成员姓名、资产名称、账号等身份信息（可通过日志验证）。
- 历史报告保留最近 6 份，第 7 份生成后最旧一份自动删除。
- `ai_enabled == False` 时所有 `/api/v1/ai/` 端点返回 403，前端展示引导而非空白页。

---

## Scope Boundaries

- 不包含报告的邮件/推送通知（月度自动生成后不主动通知用户，用户下次进入报告页时看到新报告）。
- 不包含报告内容的编辑或用户标注功能。
- 不包含跨家庭的报告对比或基准数据（无匿名化行业对标）。
- 不包含报告的 PDF 导出（截图分享已覆盖核心需求）。
- 月供压力比计算不要求用户录入收入数据——首版使用"总月供/总资产×12"作为代理指标，并在 UI 中注明这是估算值。
- AI Provider 首版支持 Anthropic Claude 和 OpenAI，不支持本地模型（Ollama 等）。

---

## Key Decisions

- **触发方式：定期自动 + 按需刷新** — 月度自动生成保证用户进入页面时有内容可看；按需刷新满足数据更新后立即重新评估的需求。
- **脱敏策略：保留精确金额，剥离身份信息** — 自托管场景下用户自己选择 AI Provider，隐私风险可控；保留精确金额使 AI 建议更具体可操作。
- **报告保留最近6份** — 平衡历史对比价值与自托管存储成本；6份覆盖半年趋势，足够判断方向。
- **LLM 只生成叙事文本，结构化数据后端计算** — 避免 LLM 幻觉污染关键财务数字；报告 JSON 结构稳定，前端渲染不依赖 LLM 输出格式。
- **独立 `agent/` 模块，通过内部 HTTP 调用获取数据** — `agent/` 通过调用 `/api/v1/dashboard/*` 等端点获取聚合数据，不直接访问数据库，不共享 SQLAlchemy session。真正解耦，可独立测试和替换 LLM Provider；调用时使用 service-to-service token 认证（不复用用户 JWT）。

---

## Dependencies / Assumptions

- 依赖 R0-R6（AI 基础设施前提）先行建设，体检报告是第一个消费这些基础设施的功能。
- APScheduler 已在 `backend/app/scheduler.py` 中运行（`AsyncIOScheduler`），新增月度报告任务只需 `scheduler.add_job()`。
- 假设 LLM API 调用平均耗时 3-8 秒；WebSocket 连接超时设为 30 秒，超时后前端展示错误提示。
- `agent/` 模块通过内部 HTTP 调用 backend 的 `/api/v1/dashboard/*` 端点获取聚合数据，使用 service-to-service token（环境变量 `AGENT_INTERNAL_TOKEN`）认证，不直接访问数据库。
- API Key 加密使用 `cryptography` 库（`Fernet` / AES-256），密钥从环境变量 `AI_ENCRYPTION_KEY` 读取。

---

## Outstanding Questions

### Resolve Before Planning

无阻塞问题。

### Deferred to Planning

- **[影响 R1][技术]** `ai_api_key_encrypted` 存储在 `Family` 表还是独立的 `ai_configs` 表？独立表便于未来支持多 Provider 配置。
- **[影响 R9][技术]** 月度定时任务如何处理多实例部署（多个 Docker 容器同时触发）？需要分布式锁或任务幂等设计。
- **[影响 R8][技术]** WebSocket 连接鉴权方式：JWT token 通过 query param 传入（`?token=xxx`）还是首条消息携带？需在规划时确认 FastAPI WebSocket 鉴权最佳实践。
- **[影响 R0][技术]** `AGENT_INTERNAL_TOKEN` 和 `AI_ENCRYPTION_KEY` 需新增到 `config.py` Settings 并在 Docker Compose 中配置。

---

## Next Steps

→ 解决上方“Resolve Before Planning”中的问题后，`/ce:plan` 进行结构化实现规划。
