# Adapter 层文件职责

> 所有 DeerFlow 行为扩展走 `services/deerflow_adapter/`。

| 文件 | 职责 |
|------|------|
| `adapter.py` | 主桥接 — typed_stream_dispatch, raw_stream_dispatch |
| `family_adapter_cache.py` | 按家庭 LRU 缓存 + EffectiveConfigBuilder 临时 config |
| `client_factory.py` | 构建 DeerFlowClient |
| `numina_deerflow_client.py` | Numina 子类（替代 monkey-patch） |
| `sync_tool_patch.py` | 5 个运行时 patch — 同步包装、ContextVar 传播、MCP 代理、工具过滤 |
| `memory_config_bridge.py` | DeerMem 配置桥接 |
| `active_skill_context.py` | 当前 skill ContextVar |
| `original_user_content_context.py` | 原始用户内容 ContextVar |
| `patched_reasoning_chat.py` | Qwen/Anthropic extended thinking + reasoning_content 统一补丁 |
| `patched_anthropic.py` | Anthropic thinking block 捕获 + reasoning_content 复制 |
| `exceptions.py` | DeerFlowError / SkillNotFoundError / TimeoutError |

## sync_tool_patch.py — 5 个 Patch

详见 SKILL.md §MCP 租户管理。入口: `apply_sync_tool_patches()`。

1. `_patched_get_available_tools`: 同步包装 + active skill 工具过滤
2. `_apply_original_user_content_patch`: 原始用户内容 ContextVar 传播
3. `_apply_extensions_config_path_patch`: extensions_config 路径 ContextVar 传播
4. `_apply_mcp_httpx_factory_patch`: httpx client factory 注入（跨线程安全）
5. `_apply_mcp_cache_threading_lock_patch`: asyncio.Lock → threading.Lock（防死锁）
