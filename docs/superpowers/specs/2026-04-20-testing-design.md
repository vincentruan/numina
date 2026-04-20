# Testing Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 测试规范，确保测试统一性和可重复性

---

## Problem

测试缺乏统一规范，不同测试脚本使用不同账号和数据，导致数据冲突和测试不可重复。测试数据污染生产环境，新成员难以理解和运行测试套件。

---

## Goals

1. 确保测试结果可重复、可验证
2. 定义统一测试账号和数据范围
3. 避免测试数据污染生产环境
4. 便于 CI/CD 集成

---

## Architecture

### 测试分类与位置

| 测试类型 | 位置 | 运行方式 | 说明 |
|----------|------|----------|------|
| 后端单元测试 | `backend/tests/` | pytest | FastAPI TestClient + in-memory SQLite |
| E2E 验收测试 | `tests/e2e/` | Shell 脚本 | API 端点验收测试 |
| E2E 扩展测试 | `tests/e2e/` | Shell 脚本 | CRUD 全流程测试 |
| 截图测试 | `tests/screenshot/` | Node.js + Puppeteer | UI 视觉回归测试 |
| 测试数据生成 | `tests/data/` | Shell 脚本 | 完整测试数据种子 |

---

## Implementation Details

### 统一测试账号

所有测试脚本使用同一账号，避免重复创建：

| 字段 | 值 | 说明 |
|------|-----|------|
| 用户名 | `demouser` | 固定测试用户名 |
| 密码 | `DemoPass123` | 固定测试密码 |
| 家庭名 | `Demo Family` | 固定测试家庭 |

账号创建时机：
- `tests/data/seed-data.sh` 首次运行时自动创建
- 后端单元测试使用 fixture 创建临时账号

### 测试数据范围

| 类型 | 数量 | 总价值 | 覆盖范围 |
|------|------|--------|----------|
| 实物资产 | 19 项 | — | 覆盖全部 13 个实物分类 |
| 金融资产 | 11 项 | — | 覆盖全部 8 个金融分类 |
| 负债 | 3 项 | ¥5,480,000 | 房贷、车贷、信用卡 |
| 心愿 | 5 项 | — | 不同优先级和状态 |
| 总资产价值 | — | ¥50,792,000 | — |
| 总负债 | — | ¥5,480,000 | — |
| 净资产 | — | ¥45,312,000 | — |

### 后端单元测试

**位置**：`backend/tests/`
**框架**：pytest + FastAPI TestClient
**数据库**：in-memory SQLite（每次测试独立数据库）

**测试文件结构**

```
backend/tests/
├── conftest.py          # Fixtures: db, client, auth_headers, second_user_headers
├── test_auth.py         # 10 tests: register, login, refresh, join-family
├── test_assets.py       # 11 tests: CRUD, daily cost, return rate
├── test_liabilities.py  # 8 tests: CRUD, payment, payoff
└── test_dashboard.py    # 7 tests: overview, allocation, trend
```

**关键 Fixtures**

```python
# conftest.py
@pytest.fixture
def db():
    # 创建 in-memory SQLite
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    session = Session()
    seed_categories(session)  # 预置分类
    yield session
    session.close()

@pytest.fixture
def auth_headers(client):
    # 注册用户并获取 token
    response = client.post("/auth/register", json={
        "username": "testuser",
        "password": "TestPass123",
        "display_name": "Test User"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### E2E 测试

**运行前置条件**
- Docker 服务运行（`docker-compose up -d`）
- 测试数据已生成（`./tests/data/seed-data.sh`）

**验收测试**（`tests/e2e/acceptance.sh`）
- 登录流程验证
- 资产 CRUD 基本功能
- 负债 CRUD 基本功能
- 仪表盘数据展示

**扩展测试**（`tests/e2e/extended.sh`）
- 心愿 CRUD 全流程
- 心愿实现为资产
- 负债还款记录
- 数据导出功能

### 截图测试

**位置**：`tests/screenshot/capture.js`
**工具**：Node.js + Puppeteer
**覆盖页面**：至少 15 个核心页面

**截图页面列表**

| 页面 | 路由 | 截图文件 |
|------|------|----------|
| 登录 | /login | login.png |
| 仪表盘 | /dashboard | dashboard.png |
| 资产列表 | /assets | assets-list.png |
| 资产详情 | /assets/:id | asset-detail.png |
| 资产创建 | /assets/new | asset-create.png |
| 负债列表 | /liabilities | liabilities-list.png |
| 心愿列表 | /wishes | wishes-list.png |
| 家庭管理 | /family | family.png |
| 设置 | /settings | settings.png |
| 分类管理 | /categories | categories.png |

### 数据生成脚本

**位置**：`tests/data/seed-data.sh`
**运行时机**：首次测试前，或需要重置数据时

**脚本功能**
1. 检查 demouser 是否存在，不存在则创建
2. 创建 19 项实物资产（覆盖 13 个分类）
3. 创建 11 项金融资产（覆盖 8 个分类）
4. 创建 3 项负债
5. 创建 5 项心愿
6. 输出数据汇总

**重复运行保障**
```bash
# 检查用户是否存在
USER_EXISTS=$(curl -s "$API/auth/login" -d "username=demouser&password=DemoPass123" | grep "access_token")

if [ -z "$USER_EXISTS" ]; then
  # 用户不存在，创建新用户
  curl -s "$API/auth/register" -d "..."
fi
```

---

## Verification

- `backend/tests/` 所有单元测试通过（36 tests）
- E2E 测试脚本运行成功，无 API 错误
- 截图测试生成至少 15 张截图
- 重复运行 `seed-data.sh` 不产生重复数据

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 测试数据生成 | `tests/data/seed-data.sh` |
| E2E 验收测试 | `tests/e2e/acceptance.sh` |
| E2E 扩展测试 | `tests/e2e/extended.sh` |
| 截图测试 | `tests/screenshot/capture.js` |
| 后端单元测试 | `backend/tests/` |
| 测试 Fixtures | `backend/tests/conftest.py` |
| 测试规范文档 | `tests/docs/TEST_SPEC.md` |

---

## Related Specs

- **编码规范设计**：`2026-04-20-coding-standards-design.md` — 测试代码规范
- **Git 工作流设计**：`2026-04-20-git-workflow-design.md` — CI/CD 集成