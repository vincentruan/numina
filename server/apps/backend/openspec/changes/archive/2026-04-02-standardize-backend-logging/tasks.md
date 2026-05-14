## 1. 创建日志配置模块

- [x] 1.1 创建 `app/core/__init__.py` 模块初始化文件
- [x] 1.2 创建 `app/core/logging_config.py` 日志配置模块
- [x] 1.3 实现日志格式配置和级别配置
- [x] 1.4 实现日志轮转功能（按大小和按时间）
- [x] 1.5 实现日志归档功能（压缩旧日志）
- [x] 1.6 实现日志清理功能（删除过期日志）

## 2. 更新配置文件

- [x] 2.1 在 `app/config.py` 中添加日志配置项
- [x] 2.2 添加 `LOG_LEVEL`、`LOG_DIR`、`LOG_MAX_BYTES` 等配置

## 3. 更新应用入口

- [x] 3.1 在 `app/main.py` 中初始化日志配置
- [x] 3.2 应用启动时执行日志清理任务

## 4. 更新现有日志使用

- [x] 4.1 更新 `app/services/security_log.py` 使用统一日志配置
- [x] 4.2 更新 `app/services/exchange_rate.py` 使用统一日志配置
- [x] 4.3 更新 `app/scheduler.py` 使用统一日志配置
- [x] 4.4 更新 `app/config.py` 使用统一日志配置

## 5. 测试和验证

- [x] 5.1 创建日志配置测试文件 `tests/test_logging_config.py`
- [x] 5.2 测试日志轮转功能
- [x] 5.3 测试日志清理功能
- [x] 5.4 验证日志格式一致性