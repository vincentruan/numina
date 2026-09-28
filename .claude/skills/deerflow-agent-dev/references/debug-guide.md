# Agent 调试指南

> 常见症状及排查方向。

| 症状 | 排查方向 |
|------|----------|
| 工具返回成功但无效果 | ContextVar 未传播（尤其 executor 线程内） |
| MCP 工具列表跨家庭泄漏 | extensions_config 环境变量竞争 |
| Harness 静默降级 | 异常被吞 — 查 `except Exception` 是否 log + re-raise |
| thinking 内容出现在标题/suggestion | `_extract_text_from_content_blocks()` 缺失 — 查所有 title/suggestion 写入路径 |
| Stream 提前关闭 / 消息停留在 processing | SSE proxy 用 `aiter_text()` 而非 `aiter_lines()`；检查 `resp.aiter_text()` 用法 |
| MCP asyncio 死锁 | 跨线程 Lock（asyncio.Lock vs threading.Lock）— 查 sync_tool_patch |
| 模型 endpoint 不匹配 | provider 字段与 base_url wire format 不一致（GLM/Qwen thinking 用 openai_compatible + `/v1`） |
| 429 / rate limit | 熔断器状态检查 + cascade fallback |
| generator yield 类型错误 | 改 yield 类型时是否更新了所有 `async for chunk in <gen>` 调用点 |
