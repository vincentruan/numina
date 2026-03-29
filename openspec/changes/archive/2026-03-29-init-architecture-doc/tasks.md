## 1. 架构文档

- [ ] 1.1 创建 docs/ARCHITECTURE.md 文件
- [ ] 1.2 编写技术栈说明（前端 Vue3 + 后端 FastAPI + 数据库）
- [ ] 1.3 使用 Mermaid 绘制系统架构图
- [ ] 1.4 使用 Mermaid 绘制模块划分图
- [ ] 1.5 编写技术选型理由说明

## 2. 数据模型文档

- [ ] 2.1 创建 docs/DATA_MODELS.md 文件
- [ ] 2.2 使用 Mermaid 绘制 ER 图（User, Family, Asset, Category, Liability, Wish）
- [ ] 2.3 编写 Asset 模型字段说明（含 asset_type, status, usage_frequency 等枚举）
- [ ] 2.4 编写资产分类体系说明（13 实物 + 8 金融）
- [ ] 2.5 编写计算字段说明（daily_cost, return_rate 公式）

## 3. API 规范文档

- [ ] 3.1 创建 docs/API_SPEC.md 文件
- [ ] 3.2 编写认证方式说明（JWT Bearer Token）
- [ ] 3.3 按模块列出 API 端点（/auth, /assets, /liabilities, /wishes, /family, /dashboard）
- [ ] 3.4 定义标准请求响应格式
- [ ] 3.5 定义错误码列表

## 4. 前端组件索引

- [ ] 4.1 创建 docs/FRONTEND_COMPONENTS.md 文件
- [ ] 4.2 编写页面路由映射表
- [ ] 4.3 编写核心组件职责说明（AssetForm, CategoryGrid, UsageFreqSelector 等）
- [ ] 4.4 编写 Store 结构说明
- [ ] 4.5 编写 API 调用约定

## 5. 编码规范文档

- [ ] 5.1 创建 docs/CODING_STANDARDS.md 文件
- [ ] 5.2 定义 Vue 3 Composition API 编码风格
- [ ] 5.3 定义 FastAPI + SQLAlchemy 编码风格
- [ ] 5.4 定义命名约定（文件、变量、函数、类）
- [ ] 5.5 定义注释要求

## 6. Git 工作流文档

- [ ] 6.1 创建 docs/GIT_WORKFLOW.md 文件
- [ ] 6.2 定义分支策略（main, feature/*, fix/*）
- [ ] 6.3 定义 Commit 格式（类型前缀 + 描述）
- [ ] 6.4 定义 PR 流程
- [ ] 6.5 定义代码审查要求

## 7. 文档整合

- [ ] 7.1 更新 README.md 添加文档链接
- [ ] 7.2 清理 docs/ 目录下的临时文档
- [ ] 7.3 提交所有文档到 Git