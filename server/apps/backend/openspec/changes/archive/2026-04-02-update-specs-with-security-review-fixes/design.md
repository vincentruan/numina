## Context

安全审计代码审查发现实现细节与规范存在偏差，需要更新规范文档以保持一致性。本次变更主要补充以下规范内容：

1. **安全日志轮转** - 实现已使用 TimedRotatingFileHandler，但规范未记录轮转策略
2. **bcrypt rounds 配置** - 实现已确保 dummy hash 使用配置的 rounds，但规范未明确说明
3. **速率限制权衡** - 实现已记录设计决策，但规范缺少权衡说明

当前架构采用 FastAPI + SQLAlchemy，安全模块包括：
- `security_log.py` - 安全事件日志
- `auth.py` - 认证服务（含时间攻击防护）
- `rate_limit.py` - 全局 API 限流中间件

## Goals / Non-Goals

**Goals:**
- 更新 `security-logging` spec，增加日志轮转要求
- 更新 `api-spec` spec，明确 bcrypt rounds 配置适用于所有哈希场景
- 更新 `rate-limiting` spec，增加权衡说明

**Non-Goals:**
- 不修改代码实现（已实现完成）
- 不添加新的安全功能
- 不修改 API 接口

## Decisions

### D1: 日志轮转策略

**Decision:** 使用 `TimedRotatingFileHandler` 实现日志轮转，每天午夜轮转，保留 7 天。

**Alternatives Considered:**
- 手动实现轮转：不选，增加代码复杂度
- 不轮转：不选，生产环境日志文件会无限增长

**Rationale:** Python 标准库提供的轮转方案成熟稳定，7 天保留期足够审计需求，同时控制磁盘占用。

### D2: bcrypt rounds 配置一致性

**Decision:** `BCRYPT_ROUNDS` 配置适用于所有密码哈希场景，包括时间攻击防护中的 dummy hash。

**Alternatives Considered:**
- dummy hash 使用固定 rounds：不选，可能导致时间不一致
- 单独配置 dummy hash rounds：不选，增加配置复杂度

**Rationale:** 保持 rounds 一致确保时间攻击防护的有效性，无论用户是否存在，bcrypt 验证时间一致。

### D3: 规范记录权衡说明

**Decision:** 在 spec 中记录速率限制的设计权衡，帮助未来维护者理解架构决策。

**权衡内容:**
- 用户名 vs IP 限流的选择
- 内存存储 vs 分布式存储的局限
- 单 worker vs 多 worker 部署的影响

**Rationale:** 规范文档应包含设计决策背景，便于未来维护和扩展。

## Risks / Trade-offs

### Risk: 规范更新与实现不同步
→ **Mitigation:** 本次变更仅补充规范，实现已完成并测试通过，无风险

### Trade-off: 不重构现有规范结构
→ **Impact:** 保持现有规范结构不变，仅增量补充，减少改动范围