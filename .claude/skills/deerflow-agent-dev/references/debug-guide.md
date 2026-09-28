# Agent 调试指南

> 常见症状及排查方向。

| 症状 | 排查方向 |
|------|----------|
| 工具返回成功但无效果 | ContextVar 未传播 |
| MCP 工具列表跨家庭泄漏 | extensions_config 环境变量竞争 |
| Harness 静默降级 | 异常被吞 |
| thinking 内容出现在标题 | 标题中间件未过滤 thinking blocks |
| Stream 提前关闭 | SSE 连接中断 |
| MCP asyncio 死锁 | 跨线程 Lock（asyncio.Lock vs threading.Lock） |
| 模型 endpoint 不匹配 | provider 配置错误 |
| 429 / rate limit | 熔断器状态检查 + cascade fallback |
