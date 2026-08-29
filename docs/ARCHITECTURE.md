# Numina 架构文档

## 系统架构

```mermaid
graph TB
    subgraph "客户端"
        Browser[浏览器 / 移动端]
    end

    subgraph "前端层"
        Nginx[Nginx 反向代理<br/>:80/:443]
        MainApp[成人端 Vue 3<br/>:5173]
        ChildApp[儿童端 Vue 3<br/>:5174]
    end

    subgraph "后端层"
        Backend[Backend API<br/>FastAPI :8000]
        Agent[AI Agent<br/>DeerFlow :8001]
        Worker[Scheduler Worker<br/>:8002]
    end

    subgraph "数据层"
        DB[(SQLite / PostgreSQL / MySQL)]
        FS[文件存储<br/>本地 / 远程]
    end

    Browser --> Nginx
    Nginx --> MainApp
    Nginx --> ChildApp
    Nginx --> Backend
    Backend --> DB
    Backend --> FS
    Backend --> Agent
    Worker --> DB
    Worker --> Agent
    Agent --> DB
```

## 模块划分

### 后端服务

| 服务 | 端口 | 职责 |
|------|------|------|
| **Backend** | 8000 | REST API、认证、资产管理、家庭管理、仪表盘、通知 |
| **Agent** | 8001 | AI 对话、技能执行、MCP 工具、DeerFlow 集成 |
| **Scheduler Worker** | 8002 | 定时任务、提醒通知、数据聚合、报表生成 |

### 后端模块

```mermaid
graph LR
    subgraph "认证 (auth)"
        Login[登录/注册]
        Token[JWT Token]
        FamilyJoin[加入家庭]
        Altcha[Altcha 验证]
    end

    subgraph "资产 (asset)"
        AssetCRUD[资产增删改查]
        Category[分类管理]
        Tag[标签管理]
        Valuation[估值历史]
        Sell[出售/处置]
    end

    subgraph "负债 (liability)"
        LiabilityCRUD[负债增删改查]
        Payment[还款记录]
        Amortization[摊销计算]
    end

    subgraph "租约 (rental)"
        ContractCRUD[租约管理]
        Landlord[房东视图]
        Tenant[租客视图]
        Dashboard[租约仪表盘]
    end

    subgraph "家庭 (family)"
        Member[成员管理]
        Invite[邀请码]
        Settings[家庭设置]
        Manifesto[家庭宣言]
    end

    subgraph "儿童 (baby/child)"
        Chore[家务管理]
        StarCoin[星星币]
        BlindBox[盲盒抽奖]
        Literacy[财商素养]
        Wish[心愿管理]
    end

    subgraph "仪表盘 (dashboard)"
        Overview[总览]
        Trend[趋势分析]
        Allocation[资产分布]
        Narrative[AI 叙事]
        FinanceCoach[财务教练]
    end

    subgraph "AI (ai)"
        Chat[对话聊天]
        Skills[技能系统]
        MCP[MCP 工具]
        Tasks[异步任务]
    end

    subgraph "通知 (notification)"
        Reminder[提醒管理]
        Push[推送通知]
        Threshold[阈值告警]
    end
```

### 前端应用

| 应用 | 端口 | 职责 |
|------|------|------|
| **Main (成人端)** | 5173 | 资产管理、负债管理、租约、仪表盘、AI 聊天、家庭管理、儿童管理 |
| **Child (儿童端)** | 5174 | 心愿、任务、星星币、盲盒、徽章、财商学习 |

### 共享包

| 包 | 说明 |
|------|------|
| **@numina/auth** | 认证 stores、组件、Axios 拦截器 |
| **@numina/math** | 纯业务计算函数（日均成本、收益率等） |
| **server/packages/core** | 基础设施：配置、Snowflake ID、熔断器 |
| **server/packages/db** | SQLAlchemy 模型、数据库会话管理 |
| **server/packages/domain** | 领域逻辑、计算函数 |
| **server/packages/security** | JWT 认证、bcrypt 加密、文件加密 |
| **server/packages/storage** | 文件存储后端、加密存储 |

## 数据流向

### 资产录入流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant API as Backend API
    participant DB as 数据库

    User->>Frontend: 填写资产表单
    Frontend->>Frontend: 表单验证 (Vant)
    Frontend->>API: POST /api/assets
    API->>API: JWT 认证 + 权限验证
    API->>API: Pydantic 数据验证
    API->>DB: 插入资产记录 (Snowflake ID)
    DB-->>API: 返回资产 ID
    API-->>Frontend: 201 Created
    Frontend-->>User: 显示成功提示
```

### AI 对话流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant API as Backend API
    participant Agent as AI Agent
    participant LLM as LLM Provider

    User->>Frontend: 发送消息
    Frontend->>API: POST /api/ai/chat (SSE)
    API->>Agent: 转发消息
    Agent->>Agent: 技能路由 (chat/coach/report)
    Agent->>Agent: 加载 MCP 工具
    Agent->>LLM: 流式请求
    LLM-->>Agent: 流式响应
    Agent->>Agent: 工具调用 (如需)
    Agent-->>API: SSE 事件流
    API-->>Frontend: SSE 转发
    Frontend-->>User: 实时渲染
```

### AI 任务异步流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant API as Backend API
    participant Worker as Scheduler Worker
    participant Agent as AI Agent

    User->>Frontend: 触发生成 (报告/叙事)
    Frontend->>API: POST /api/ai/tasks
    API->>API: 创建 AITask 记录
    API-->>Frontend: 返回 task_id
    Frontend->>Frontend: useTaskPolling 轮询
    Worker->>Agent: 执行 AI 任务
    Agent-->>Worker: 返回结果
    Worker->>API: 更新任务状态
    Frontend->>API: GET /api/ai/tasks/{id}
    API-->>Frontend: 任务结果
    Frontend-->>User: 显示结果
```

## AI 技能系统

Agent 采用基于 DeerFlow 的技能系统架构：

| 技能 | 触发方式 | 说明 |
|------|----------|------|
| **chat** | 默认对话 | 通用对话，可搜索家庭数据 |
| **chat-search** | Web 搜索开启 | 带联网搜索的对话 |
| **finance-coach** | /ai/chat skill=finance-coach | 个性化财务建议 |
| **asset-report** | /ai/chat skill=asset-report | 资产分析报告 |
| **wish-advice** | /ai/chat skill=wish-advice | 心愿评估建议 |
| **dashboard-narrative** | 异步任务 | 仪表盘 AI 摘要 |
| **literacy-weekly-report** | 异步任务 | 儿童财商周报 |
| **import-parse** | 文件导入 | 解析导入文件 |
| **skill-creator** | 管理页面 | 创建自定义技能 |
| **skill-installer** | 管理页面 | 安装社区技能 |

### MCP 工具集成

Agent 支持 MCP (Model Context Protocol) 工具：

| 类别 | 工具 |
|------|------|
| **数据查询** | 资产列表、负债列表、家庭概览、成员信息 |
| **数据写入** | 批量创建资产、批量更新、批量删除 |
| **文件处理** | 文件上传、PDF 识别 (Vision) |
| **Web 搜索** | 联网搜索 (可选) |

## 技术选型理由

| 决策 | 理由 |
|------|------|
| Vue 3 + Composition API | 复杂逻辑复用，TypeScript 原生支持 |
| Vant 4 | 移动端 H5 组件库，组件丰富，暗黑模式支持 |
| Pinia | 比 Vuex 更简洁，TypeScript 支持更好 |
| ECharts | 图表功能强大，配置灵活，移动端适配好 |
| FastAPI | 异步支持好，自动生成 API 文档，类型提示友好 |
| SQLAlchemy 2.0 | 成熟稳定，支持多种数据库，迁移工具完善 |
| DeerFlow | 成熟的 AI Agent 框架，支持多 Provider、中间件、工具调用 |
| SQLite (默认) | 零配置部署，适合家庭场景；可选 PostgreSQL/MySQL 扩展 |
| Snowflake ID | 分布式 ID 生成，序列化安全（JS 精度范围内） |
| Docker Compose | 一键部署，环境隔离，易于迁移 |

## 部署架构

```mermaid
graph TB
    subgraph "Docker Compose"
        Nginx[Nginx<br/>反向代理]
        Backend[Backend<br/>FastAPI]
        Agent[Agent<br/>DeerFlow]
        Worker[Worker<br/>Scheduler]
        FrontendMain[Frontend Main<br/>Vue 3]
        FrontendChild[Frontend Child<br/>Vue 3]
        DB[(数据库<br/>SQLite/PG)]
    end

    Internet[外部访问<br/>:80/:443] --> Nginx
    Nginx --> FrontendMain
    Nginx --> FrontendChild
    Nginx --> Backend
    Backend --> Agent
    Backend --> Worker
    Backend --> DB
    Worker --> DB
    Agent --> DB
```

### 部署模式

| 模式 | 说明 |
|------|------|
| **本地构建** | `make deploy` — docker compose build + up |
| **预构建镜像** | `make deploy-images` — 拉取 GHCR 镜像 |
| **本地编译远程部署** | `make deploy-local` — 本地 build + 打包 + rsync 到远程服务器 |
| **开发模式** | `make deploy-dev` — 放宽安全检查 + 种子数据 |

## 安全架构

| 层面 | 措施 |
|------|------|
| **认证** | JWT (access_token 30min + refresh_token 7d)，Altcha 防机器人验证 |
| **密码** | bcrypt 哈希，不可逆 |
| **授权** | 家庭级数据隔离，角色区分 (家长/孩子/管理员) |
| **传输** | HTTPS (Nginx 配置)，CORS 白名单 |
| **存储** | 文件加密 (Fernet)，AI 数据加密 |
| **审计** | 安全审计日志，设备会话管理 |
| **API 安全** | 速率限制，输入验证 (Pydantic)，Snowflake ID 防枚举 |
