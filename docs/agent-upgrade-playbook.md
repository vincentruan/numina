# Agent 升级与回滚手册

本手册说明如何升级 DeerFlow 版本、如何灰度开启 DeerFlow 路径、以及如何在出现问题时快速回滚。

## 升级 DeerFlow

### 步骤

1. 更新参考工程：

   ```bash
   cd ../deer-flow-reference
   git pull origin main
   ```

2. 运行 vendor 脚本将新版本复制到 agent：

   ```bash
   cd numina/agent
   ./scripts/vendor-deerflow.sh
   ```

3. 检查 `.vendor-manifest.json` 确认 commit SHA 已更新。

4. 运行兼容性补丁（如需要）：

   ```bash
   uv run python scripts/patch-langgraph-runtime.py
   ```

5. 重新安装依赖：

   ```bash
   uv sync
   ```

6. 运行全量测试：

   ```bash
   uv run pytest tests/ -v
   ```

7. 如测试通过，提交变更：

   ```bash
   git add vendor/ .vendor-manifest.json pyproject.toml uv.lock
   git commit -m "chore(agent): upgrade deerflow-harness to <commit-sha>"
   ```

### 版本锁定

`pyproject.toml` 中的 LangChain/LangGraph 版本必须与 DeerFlow 的 `uv.lock` 保持一致。升级后检查：

```bash
grep "langchain\|langgraph" vendor/deerflow-harness/uv.lock | head -20
```

## 开启 DeerFlow 路径

### 灰度开启

1. 在测试/staging 环境设置：

   ```bash
   USE_DEERFLOW=true
   DEERFLOW_CONFIG_ENV=dev
   ```

2. 发送测试请求，观察 `logs/agent-audit.log` 中的 `fallback_used` 字段：
   - `fallback_used=False` + `skill_triggered=<capability>` → DeerFlow 正常工作
   - `fallback_used=True` + `error_type=<type>` → DeerFlow 失败，已降级

3. 确认无异常后，在生产环境设置：

   ```bash
   USE_DEERFLOW=true
   DEERFLOW_CONFIG_ENV=prod
   ```

### 验证健康信号

```bash
# 查看最近 10 条审计日志
tail -10 logs/agent-audit.log

# 统计 DeerFlow 成功率
grep "fallback_used=False" logs/agent-audit.log | wc -l
grep "fallback_used=True" logs/agent-audit.log | wc -l
```

## 回滚

### 快速回滚（无需重启）

设置环境变量关闭 DeerFlow 路径：

```bash
USE_DEERFLOW=false
```

下次请求起生效，无需重启服务。

### 完全回滚（恢复旧版本）

1. 关闭 DeerFlow 路径：`USE_DEERFLOW=false`
2. 回滚 vendor 目录到上一个已知正常版本：

   ```bash
   git checkout <last-good-commit> -- vendor/ .vendor-manifest.json
   uv sync
   ```

3. 重启服务。

### 回滚触发条件

出现以下情况时应立即回滚：

- `logs/agent-audit.log` 中 `fallback_used=True` 比例超过 20%
- 出现 `error_type=DeerFlowTimeoutError` 持续超过 5 分钟
- 响应时间 P95 超过 30 秒
- 出现未预期的 PII 泄露（检查 `redaction_log` 字段）

## 配置变更

### 修改 DeerFlow 配置

编辑 `deerflow_config/` 下对应环境的 `config.yaml`，重启服务生效。

**不要修改** `vendor/deerflow-harness/` 内的文件，升级时会被覆盖。

### 添加新 Skill

1. 在 `skills/custom/<skill-name>/` 下创建 `SKILL.md`
2. 按现有 skill 格式定义：适用场景、触发条件、输入约束、输出 schema、边界限制
3. 在 `deerflow_config/agents/family-finance-agent/profile.yaml` 中注册 skill
4. 运行测试验证

## 监控与观测

### 关键日志字段

| 字段 | 说明 | 健康值 |
|------|------|--------|
| `fallback_used` | 是否走了 fallback | 开启 DeerFlow 后应 < 10% |
| `duration_ms` | 请求耗时 | P95 < 15000ms |
| `error_type` | 错误类型 | 应为 null |
| `skill_triggered` | 触发的 skill | 应与 capability 一致 |

### 日志查询示例

```bash
# 查看所有失败请求
grep '"success": false\|success=False' logs/agent-audit.log

# 查看 DeerFlow 超时
grep "DeerFlowTimeoutError" logs/agent-audit.log

# 查看特定家庭的调用记录
grep "family_id=fam-xxx" logs/agent-audit.log
```
