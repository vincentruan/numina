# Supported AI Providers

Numina supports multiple AI providers for different use cases. Each provider can be configured independently in **Settings → AI**.

## Provider Overview

| Provider | Protocol | Thinking | Vision | Auth |
|----------|----------|----------|--------|------|
| Anthropic | Messages API (`/v1/messages`) | ✓ | ✓ | API Key |
| OpenAI | Responses API (`/v1/responses`) | ✓ | ✓ | API Key |
| OpenAI Compatible | Chat Completions (`/v1/chat/completions`) | ✓ (vendor-dependent) | ✓ (model-dependent) | API Key |
| Google Gemini | generateContent (Native SDK) | ✗ | ✓ | API Key |

## Anthropic

- **Models:** Claude Opus 5, Claude Sonnet 5, Claude Haiku 4.5
- **Thinking:** Native extended thinking with configurable budget
- **Vision:** Supported via base64 image input
- **Endpoint:** `https://api.anthropic.com` (configurable via `base_url`)

## OpenAI

- **Models:** GPT-5, GPT-5 mini, o-series
- **Thinking:** Reasoning effort (high/low) via Responses API
- **Vision:** Supported via image_url input
- **Endpoint:** `https://api.openai.com` (not configurable — native Responses API)

## OpenAI Compatible

Works with any OpenAI-compatible API endpoint (DashScope, vLLM, Ollama, Novita, etc.).

- **Models:** Provider-dependent (GLM-5, Qwen3, QwQ, DeepSeek-R1, etc.)
- **Thinking:** Vendor-dependent — some providers support `enable_thinking` or `reasoning_content`
- **Vision:** Model-dependent
- **Endpoint:** User-configurable via `base_url`

## Google Gemini

- **Models:** `gemini-2.5-pro`, `gemini-2.0-flash`
- **Thinking:** Not supported (Gemini native API does not expose thinking tokens)
- **Vision:** Supported via `Part.from_bytes()` image input
- **Endpoint:** Google AI Studio (fixed — `base_url` is not configurable)
- **Auth:** Google AI Studio API Key (not Vertex AI service account)

### Gemini Notes

- The `base_url` field is hidden in the settings form since Google's native API endpoint is fixed.
- Gemini supports up to 3 model slots like other providers, but `thinking_supported` is always `false`.
- For multi-step agent tasks (chat, asset-report), Numina uses `langchain-google-genai` (ChatGoogleGenerativeAI) via the DeerFlow adapter.
- For lightweight single-call tasks (suggest, input polish, title generation), Numina uses the `google-genai` SDK directly.
