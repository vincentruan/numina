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

## ⚠ Thinking 配置与 provider/endpoint 匹配（重要）

**每条 AI 配置的 `provider` 字段必须与 `base_url` 的 wire format 一致，不能只按模型厂商填**。错误组合会导致 thinking 静默失效或 404。

| provider | base_url 类型 | thinking_supported=True 时行为 |
|----------|---------------|-------------------------------|
| `anthropic` | Anthropic-compatible (`/apps/anthropic` 等) | 仅原生 Claude 模型可用；GLM/Qwen 指向此 endpoint 时 thinking **被静默忽略** |
| `openai` / `openai_compatible` | OpenAI-compatible (`/v1`) | GLM-5 / Qwen3 / QwQ 的 thinking 通过此 endpoint 可用 |

典型错误：`provider="anthropic"` + `base_url=DashScope Anthropic endpoint` + `thinking_supported=True` → `deep_think=true` 请求直接跳过 thinking phase，stream 里没有 `phase.thinking` 事件。

修复方法：`provider` 改为 `openai_compatible`，`base_url` 改为 OpenAI-compatible endpoint（`/v1` 后缀），并清空 adapter cache（`POST /internal/cache/invalidate/{family_id}`）。

详见：`docs/solutions/integration-issues/deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md`

## Thinking 路由 (`_THINKING_CLASS_OVERRIDES`)

| 类型 | Class | 触发条件 |
|------|-------|----------|
| `deepseek` | `PatchedChatDeepSeek` | `extra_body.thinking.{type: enabled\|disabled}` |
| `reasoning` | `PatchedChatReasoning` | Qwen/GLM/QwQ via DashScope — `extra_body.enable_thinking` |
| `anthropic` | `PatchedChatAnthropic` | `thinking.budget_tokens` (fraction of max_tokens) |

**规则**: thinking 模型返回的 `response.content` 可能是 block list（`[{"type":"thinking",...},{"type":"text",...}]`），任何字符串消费方（标题、suggestion、metadata）必须用 `_extract_text_from_content_blocks()`，不得直接 `str(content)`。详见 [references/debug-guide.md](references/debug-guide.md) §thinking-block 泄漏。

## max_tokens 解析优先级

1. `ai_provider['max_tokens']` — DB 用户设置
2. `system-config.yaml` prefix-matched default
3. `None` — SDK / vendor defaults

## 熔断 & 降级

- **三态 FSM 熔断器**（per provider）：closed → open → half-open
- **Cascade retry**: 主 provider 失败 → fallback provider
- **Web search circuit**: `report_web_search_circuit()` 报告搜索 provider 故障
- 故障分类：`transient_timeout`, `transient_rate_limit`, `transient_network`, `permanent_auth`, `transient_server`
