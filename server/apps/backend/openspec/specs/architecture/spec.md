## Requirements

### Requirement: 架构必须包含日志配置模块

系统 SHALL 在 `backend/app/core/` 目录下定义日志配置模块，包含以下文件：
- `__init__.py` - 模块初始化
- `logging_config.py` - 日志配置模块

#### Scenario: 日志配置模块结构

- **WHEN** 开发者查看日志配置代码
- **THEN** 可以看到清晰的日志配置定义和实现

### Requirement: 架构必须定义日志目录结构

系统 SHALL 定义以下日志目录结构：
```
logs/
├── app.log              # 应用主日志
├── app.log.1            # 轮转备份文件
├── security.log         # 安全事件日志
├── security.log.1       # 安全日志轮转备份
└── archive/             # 归档目录（可选）
    └── *.log.gz         # 压缩归档日志
```

#### Scenario: 日志目录自动创建

- **WHEN** 应用启动时日志目录不存在
- **THEN** 系统自动创建 `logs/` 目录及子目录