# Numina 项目架构

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.5+ | 前端框架 |
| Vite | 8.0+ | 构建工具 |
| Vant | 4.9+ | 移动端 UI 组件库 |
| Pinia | 3.0+ | 状态管理 |
| Vue Router | 4.6+ | 路由管理 |
| ECharts | 6.0+ | 图表可视化 |
| Axios | 1.13+ | HTTP 客户端 |
| TypeScript | 5.9+ | 类型支持 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115+ | Web 框架 |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.14+ | 数据库迁移 |
| Pydantic | 2.10+ | 数据验证 |
| python-jose | 3.3+ | JWT 认证 |
| APScheduler | 3.11+ | 定时任务 |

### 数据库

- **开发环境**: SQLite（内存模式用于测试）
- **生产环境**: MySQL 8.0+ / PostgreSQL 14+

### 部署

- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx

## 系统架构图

```mermaid
graph TB
    subgraph "客户端"
        Browser[浏览器]
        Mobile[移动端浏览器]
    end

    subgraph "前端层"
        Nginx[Nginx 反向代理]
        Vue[Vue 3 应用]
    end

    subgraph "后端层"
        FastAPI[FastAPI 服务]
        Auth[认证模块]
        Asset[资产模块]
        Liability[负债模块]
        Wish[心愿模块]
        Family[家庭模块]
        Dashboard[仪表盘模块]
    end

    subgraph "数据层"
        MySQL[(MySQL/PostgreSQL)]
        Redis[(Redis 缓存)]
    end

    Browser --> Nginx
    Mobile --> Nginx
    Nginx --> Vue
    Nginx --> FastAPI
    FastAPI --> Auth
    FastAPI --> Asset
    FastAPI --> Liability
    FastAPI --> Wish
    FastAPI --> Family
    FastAPI --> Dashboard
    Auth --> MySQL
    Asset --> MySQL
    Liability --> MySQL
    Wish --> MySQL
    Family --> MySQL
    Dashboard --> MySQL
```

## 模块划分

```mermaid
graph LR
    subgraph "认证模块 (auth)"
        Login[登录/注册]
        Token[Token 管理]
        FamilyJoin[加入家庭]
    end

    subgraph "资产模块 (asset)"
        AssetCRUD[资产增删改查]
        Category[分类管理]
        Tag[标签管理]
        Valuation[资产估值]
    end

    subgraph "负债模块 (liability)"
        LiabilityCRUD[负债增删改查]
        Payment[还款记录]
    end

    subgraph "心愿模块 (wish)"
        WishCRUD[心愿增删改查]
        Priority[优先级管理]
    end

    subgraph "家庭模块 (family)"
        Member[成员管理]
        Invite[邀请码]
        Snapshot[快照]
    end

    subgraph "仪表盘模块 (dashboard)"
        Overview[总览]
        Trend[趋势分析]
        Allocation[资产分布]
    end
```

## 数据流向

### 资产录入流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant API as FastAPI
    participant DB as 数据库

    User->>Frontend: 填写资产表单
    Frontend->>Frontend: 表单验证
    Frontend->>API: POST /assets
    API->>API: 权限验证
    API->>API: 数据验证
    API->>DB: 插入资产记录
    DB-->>API: 返回资产 ID
    API-->>Frontend: 返回创建成功
    Frontend-->>User: 显示成功提示
```

### 统计计算流程

```mermaid
sequenceDiagram
    participant Scheduler as 定时任务
    participant Service as 统计服务
    participant DB as 数据库

    Scheduler->>Service: 触发每日统计
    Service->>DB: 查询所有资产
    DB-->>Service: 返回资产列表
    Service->>Service: 计算日均成本
    Service->>Service: 计算收益率
    Service->>Service: 汇总分类数据
    Service->>DB: 更新统计缓存
```

## 技术选型理由

### 前端选型

| 决策 | 理由 |
|------|------|
| Vue 3 | Composition API 更适合复杂逻辑复用，性能优于 Vue 2 |
| Vant | 专为移动端设计，组件丰富，文档完善 |
| Pinia | 比 Vuex 更简洁，TypeScript 支持更好 |
| ECharts | 图表功能强大，配置灵活，社区活跃 |

### 后端选型

| 决策 | 理由 |
|------|------|
| FastAPI | 异步支持好，自动生成 API 文档，类型提示友好 |
| SQLAlchemy | 成熟稳定，支持多种数据库，迁移工具完善 |
| Pydantic | 与 FastAPI 深度集成，数据验证强大 |

### 数据库选型

| 决策 | 理由 |
|------|------|
| MySQL/PostgreSQL | 开源免费，社区活跃，性能可靠 |
| SQLite（测试） | 无需安装，适合单元测试 |

## 目录结构

```
numina/
├── frontend/                # 前端项目
│   ├── src/
│   │   ├── api/            # API 调用
│   │   ├── components/     # 组件
│   │   ├── composables/    # 组合式函数
│   │   ├── pages/          # 页面
│   │   ├── stores/         # Pinia Store
│   │   ├── router/         # 路由配置
│   │   ├── types/          # 类型定义
│   │   └── utils/          # 工具函数
│   └── package.json
│
├── backend/                 # 后端项目
│   ├── app/
│   │   ├── auth/           # 认证模块
│   │   ├── models/         # 数据模型
│   │   ├── routers/        # API 路由
│   │   ├── schemas/        # Pydantic Schema
│   │   ├── services/       # 业务逻辑
│   │   └── db/             # 数据库配置
│   ├── tests/              # 单元测试
│   └── pyproject.toml
│
├── tests/                   # 集成测试
│   ├── data/               # 测试数据
│   ├── e2e/                # E2E 测试
│   ├── screenshot/         # 截图测试
│   └── docs/               # 测试文档
│
├── docs/                    # 项目文档
├── openspec/                # OpenSpec 变更管理
└── docker-compose.yml       # Docker 配置
```