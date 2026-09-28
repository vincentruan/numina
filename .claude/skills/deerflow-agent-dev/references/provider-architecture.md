# 多模型供应商架构

> `server/apps/agent/` 的多模型供应商抽象层完整参考。

## 架构层次

```
DB ai_providers 行 (per family, Fernet-encrypted)
    ↓ EffectiveConfigBuilder.build()
    ↓ packages/core/model_entry.build_model_entry()
    ↓ 生成 DeerFlow models[0] entry
    ↓ create_chat_model() 路由到正确的 LangChain class
```

## Provider Class Map (`_PROVIDER_CLASS_MAP`)

| Provider key | LangChain class | Notes |
|-------------|-----------------|-------|
| `anthropic` | `langchain_anthropic:ChatAnthropic` | 原生 Messages API |
| `openai` | `langchain_openai:ChatOpenAI` | gpt-5*, o-series |
| `openai_compatible` | `langchain_openai:ChatOpenAI` | GLM/Qwen/DashScope/Novita/vLLM |
| `gemini` | `langchain_google_genai:ChatGoogleGenerativeAI` | 不支持 thinking |

## Thinking 路由 (`_THINKING_CLASS_OVERRIDES`)

| 类型 | Class | 触发条件 |
|------|-------|----------|
| `deepseek` | `PatchedChatDeepSeek` | `extra_body.thinking.{type: enabled\|disabled}` |
| `reasoning` | `PatchedChatReasoning` | Qwen/GLM/QwQ via DashScope — `extra_body.enable_thinking` |
| `anthropic` | `PatchedChatAnthropic` | `thinking.budget_tokens` (fraction of max_tokens) |

## max_tokens 解析优先级

1. `ai_provider['max_tokens']` — DB 用户设置
2. `system-config.yaml` prefix-matched default
3. `None` — SDK / vendor defaults

## 熔断 & 降级

- **三态 FSM 熔断器**（per provider）：closed → open → half-open
- **Cascade retry**: 主 provider 失败 → fallback provider
- **Web search circuit**: `report_web_search_circuit()` 报告搜索 provider 故障
- 故障分类：`transient_timeout`, `transient_rate_limit`, `transient_network`, `permanent_auth`, `transient_server`
