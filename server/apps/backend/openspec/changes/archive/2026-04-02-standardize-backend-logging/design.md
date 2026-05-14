## Context

Numina Backend 当前日志状态：
- 安全日志已实现轮转（`TimedRotatingFileHandler`，每天轮转，保留 7 天）
- 应用日志使用 Python 标准 `logging` 模块，但无统一配置
- 无日志归档（压缩）机制
- 无日志自动清理机制

当前日志使用位置：
- `app/main.py` - 应用启动日志
- `app/services/security_log.py` - 安全事件日志
- `app/services/exchange_rate.py` - 汇率服务日志
- `app/scheduler.py` - 定时任务日志
- `app/config.py` - 配置加载日志

## Goals / Non-Goals

**Goals:**
- 统一日志配置管理，集中管理日志格式、级别、输出位置
- 实现日志轮转，支持按大小和按时间两种模式
- 实现日志归档，自动压缩旧日志文件
- 实现日志清理，自动删除过期日志文件
- 按模块分离日志文件（应用日志、安全日志）

**Non-Goals:**
- 不实现日志聚合系统（如 ELK、Loki）
- 不实现远程日志传输
- 不修改现有日志消息内容
- 不引入第三方日志库（如 loguru）

## Decisions

### D1: 日志轮转策略

**Decision:** 使用 Python 标准 `RotatingFileHandler` 实现按大小轮转，`TimedRotatingFileHandler` 实现按时间轮转。默认采用按大小轮转（10MB），保留 10 个备份文件。

**Alternatives Considered:**
- 仅按时间轮转：不选，日志量可能在短时间内暴涨
- 第三方库 loguru：不选，引入额外依赖
- 自定义轮转逻辑：不选，标准库已足够

**Rationale:** 按大小轮转可控制单文件大小，便于查看和传输；保留多个备份确保历史可追溯。

### D2: 日志归档策略

**Decision:** 使用 `RotatingFileHandler` 的内置备份机制，自动轮转旧日志。对于需要长期保存的日志，使用 `gzip` 压缩归档。

**Alternatives Considered:**
- tar.gz 归档：不选，增加复杂度
- zip 归档：不选，gzip 更通用

**Rationale:** 标准库的轮转机制已满足需求，压缩可节省存储空间。

### D3: 日志清理策略

**Decision:** 实现定期清理任务，删除超过保留天数的日志文件。默认保留 30 天。

**Alternatives Considered:**
- 手动清理：不选，运维负担重
- 无清理：不选，磁盘空间无限增长

**Rationale:** 自动清理确保磁盘空间可控，30 天保留期足够问题排查。

### D4: 日志格式

**Decision:** 使用统一结构化日志格式：
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Alternatives Considered:**
- JSON 格式：不选，当前规模不需要
- 自定义格式：不选，标准格式足够

**Rationale:** 统一格式便于日志解析和问题排查。

## Risks / Trade-offs

### Risk: 日志文件过多占用磁盘
→ **Mitigation:** 配置合理的轮转大小和备份数量，实施自动清理

### Risk: 日志敏感信息泄露
→ **Mitigation:** 在日志配置中过滤敏感字段，生产环境限制日志级别

### Trade-off: 不使用日志聚合系统
→ **Impact:** 多实例部署时日志分散，需要手动收集；当前单机部署不受影响

### Trade-off: 不使用第三方日志库
→ **Impact:** 功能受限，但减少依赖维护成本