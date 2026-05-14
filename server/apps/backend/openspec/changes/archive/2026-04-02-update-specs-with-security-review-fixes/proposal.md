## Why

安全审计代码审查发现部分实现细节未在规范中明确记录，需要更新 spec 文档以保持规范与实现的一致性。具体包括：
- 安全日志轮转配置未在 spec 中规定
- bcrypt rounds 配置使用场景未完整说明
- 速率限制权衡设计未在 spec 中记录

## What Changes

- 安全日志规范增加日志轮转要求（7 天轮转）
- 认证规范明确 bcrypt rounds 配置适用于所有哈希场景（包括 dummy hash）
- 速率限制规范增加权衡说明和设计决策文档

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

- `security-logging`: 增加日志轮转要求（7 天轮转，防止日志文件无限增长）
- `api-spec`: 明确 bcrypt rounds 配置适用于所有密码哈希场景（包括时间攻击防护中的 dummy hash）
- `rate-limiting`: 增加速率限制权衡说明（用户名 vs IP、单 worker vs 多 worker）

## Impact

**规范文件更新**:
- `openspec/specs/security-logging/spec.md` - 新增日志轮转要求
- `openspec/specs/api-spec/spec.md` - 完善 bcrypt rounds 配置说明
- `openspec/specs/rate-limiting/spec.md` - 增加速率限制权衡说明

**代码已实现**:
- `backend/app/services/security_log.py` - 使用 TimedRotatingFileHandler
- `backend/app/services/auth.py` - dummy hash 使用配置的 bcrypt rounds
- `backend/app/middleware/rate_limit.py` - 添加设计权衡文档注释
- `backend/tests/test_rate_limit.py` - 新增速率限制集成测试

**测试覆盖**:
- 49 个安全相关测试全部通过