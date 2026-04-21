# Architecture Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** 系统整体架构、五层划分、技术选型总览

---

## Problem

系统缺乏整体架构文档，新成员难以理解技术选型理由和模块边界。代码组织分散，职责划分不清，导致维护困难和架构腐化。

---

## Goals

1. 明确技术栈和选型理由
2. 定义五层架构职责边界
3. 规范层级依赖关系
4. 作为总纲引用各层详细设计

---

## Architecture

### 技术栈总览

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 前端框架 | Vue 3 Composition API | 3.x | 更好的逻辑复用和类型支持 |
| 前端语言 | TypeScript | 5.x | 类型安全，IDE支持完善 |
| 前端构建 | Vite | 8.x | 快速开发服务器，HMR体验好 |
| 前端UI | Vant 4 | 4.x | 成熟移动端组件库，中文友好 |
| 前端图表 | ECharts | 5.x | 强大的可视化能力 |
| 前端状态 | Pinia | 2.x | Vue 3 官方状态管理 |
| 后端框架 | FastAPI | 0.100+ | 高性能、自动文档、类型安全 |
| 后端语言 | Python | 3.11 | 开发效率高，生态丰富 |
| 后端ORM | SQLAlchemy | 2.x | Mapped类型注解，现代API |
| 数据库 | SQLite | 默认 | 轻量级、零配置、适合家庭场景 |
| 数据库 | MySQL | 可选 | 支持多用户、高性能场景 |
| 数据库 | PostgreSQL | 可选 | 企业级、扩展性强 |
| 认证 | JWT | bcrypt | 标准认证方案、密码哈希安全 |
| 部署 | Docker Compose | — | 容器化部署、环境一致性 |
| 反向代理 | Nginx | — | SSL、静态资源、负载均衡 |

### 五层架构划分

| 层级 | 职责 | 核心目录 | 详细文档 |
|------|------|----------|----------|
| Data Layer | 数据持久化、实体模型、数据库抽象 | `backend/app/models/`, `backend/app/db/`, `backend/app/services/cache/` | `2026-04-21-data-layer-design.md` |
| API Layer | HTTP端点、认证机制、响应格式、速率限制 | `backend/app/routers/`, `backend/app/middleware/` | `2026-04-21-api-layer-design.md` |
| Security Layer | 安全验证、日志审计、防护机制 | `backend/app/services/file_validation.py`, `backend/app/services/security_log.py` | `2026-04-21-security-layer-design.md` |
| Frontend Layer | 页面组件、路由状态、国际化、主题 | `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/stores/` | `2026-04-21-frontend-layer-design.md` |
| DevOps Layer | 编码规范、Git工作流、测试、监控 | `backend/tests/`, `tests/`, `.github/` | `2026-04-21-devops-layer-design.md` |

### 层级依赖关系

```
Frontend Layer → API Layer → Security Layer → Data Layer
                                    ↓
                              DevOps Layer（贯穿全栈）
```

依赖规则：
- Frontend → API：前端通过 HTTP 调用 API 层
- API → Security：API 层调用安全服务进行验证和日志
- API → Data：API 层通过服务层访问数据层
- DevOps：横跨所有层，提供规范、测试、监控

---

## Implementation Details

### API 前缀

所有 API 端点使用 `/api/v1` 前缀。

### 错误响应格式

统一错误响应：`{"detail": "中文错误信息"}`

HTTP 状态码规范：
- 200: 成功（GET、PUT）
- 201: 创建成功（POST）
- 400: 参数错误
- 401: 认证失败
- 403: 权限不足
- 404: 资源不存在
- 409: 冲突（重复资源）
- 429: 请求过多（限流）
- 500: 服务器错误

---

## Code Pointers

| 入口 | 文件路径 |
|------|----------|
| 主应用 | `backend/app/main.py` |
| 配置 | `backend/app/config.py` |
| 数据库引擎 | `backend/app/database.py` |

---

## Related Specs

- **数据层设计**：`2026-04-21-data-layer-design.md`
- **API层设计**：`2026-04-21-api-layer-design.md`
- **安全层设计**：`2026-04-21-security-layer-design.md`
- **前端层设计**：`2026-04-21-frontend-layer-design.md`
- **DevOps层设计**：`2026-04-21-devops-layer-design.md`