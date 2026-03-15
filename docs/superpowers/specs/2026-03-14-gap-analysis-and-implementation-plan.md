# Numina 需求差距分析与实施计划

## 一、审计结论

对照设计规格文档，后端和前端的 MVP 核心功能已基本实现（约 95%）。以下是逐项审计后发现的所有缺口。

---

## 二、需求差距清单

### GAP-1: 前端缺少 Token 自动刷新机制（关键）

**文件**: `frontend/src/api/index.ts`
**现状**: 401 响应直接清除 token 并跳转登录页
**应有**: 401 时先尝试用 refresh token 换取新 access token，成功则重试原请求，失败才跳转登录
**影响**: 用户每 15 分钟被强制登出，体验极差

### GAP-2: 前端缺少负债还款 API 调用（关键）

**文件**: `frontend/src/api/liabilities.ts`
**现状**: 只有 CRUD 五个方法，缺少 `recordPayment()`
**应有**: `recordPayment(id: string, amount: number)` 调用 `PUT /liabilities/{id}/payment`
**影响**: 后端已实现还款端点，但前端无法调用

### GAP-3: 前端缺少负债还款 UI（关键）

**文件**: 需要在负债详情/列表页增加还款操作入口
**现状**: `LiabilityListPage.vue` 和 `LiabilityFormPage.vue` 没有还款按钮
**应有**: 负债卡片或详情页提供"记录还款"按钮，弹出金额输入框，调用还款 API
**影响**: 用户无法记录还款进度

### GAP-4: 前端缺少负债详情页（中等）

**文件**: 路由中没有 `/liabilities/:id` 详情页
**现状**: 只有列表页和编辑表单页，没有独立的详情查看页
**应有**: 类似 `AssetDetailPage.vue` 的负债详情页，展示还款进度、关联资产、利率等
**影响**: 用户只能通过编辑页查看负债信息，缺少只读详情视图

### GAP-5: 前端资产价值更新 HTTP 方法不匹配（小）

**文件**: `frontend/src/api/assets.ts:25`
**现状**: 使用 `http.patch()` 调用 `/assets/{id}/value`
**应有**: 使用 `http.put()` — 后端定义为 `@router.put("/{asset_id}/value")`
**影响**: 请求会返回 405 Method Not Allowed

### GAP-6: 缺少 Alembic 初始迁移（小）

**文件**: `backend/alembic/versions/` 目录为空
**现状**: 依赖 `Base.metadata.create_all()` 自动建表
**应有**: 生成初始迁移脚本，为后续 schema 变更做准备
**影响**: 当前可工作，但后续修改 schema 时无法增量迁移

### GAP-7: 缺少后端测试（中等）

**文件**: 无 `backend/tests/` 目录
**现状**: 没有任何自动化测试
**应有**: pytest + httpx 测试核心 API 端点（认证、资产 CRUD、仪表盘聚合）
**影响**: 无法自动验证功能正确性，重构风险高

### GAP-8: 缺少前端构建验证（小）

**现状**: 未验证 `npm run build` 是否能成功通过
**应有**: 确保 TypeScript 编译无错误，生产构建正常
**影响**: Docker 构建可能失败

### GAP-9: 缺少 Docker 端到端验证（中等）

**现状**: docker-compose.yml 存在但未验证能否正常启动
**应有**: 验证三个容器（backend、frontend、nginx）能正常启动并协同工作
**影响**: 部署可能失败

### GAP-10: 负债 store 缺少还款方法（关键）

**文件**: `frontend/src/stores/liability.ts`
**现状**: 只有 CRUD 方法
**应有**: 增加 `recordPayment(id, amount)` 方法
**影响**: 与 GAP-2/GAP-3 关联

---

## 三、实施计划

按优先级和依赖关系排序，分为 4 个阶段。

### Phase A: 关键功能修复（前端 API + UI）

#### A1. 修复资产价值更新 HTTP 方法
- **文件**: `frontend/src/api/assets.ts`
- **改动**: 第 25 行 `http.patch` → `http.put`
- **验证**: 在资产详情页点击"更新价值"，确认请求成功（200）

#### A2. 添加负债还款 API 方法
- **文件**: `frontend/src/api/liabilities.ts`
- **改动**: 新增 `recordPayment(id: string, amount: number)` 函数
- **代码**:
  ```typescript
  export function recordPayment(id: string, amount: number) {
    return http.put<Liability>(`/liabilities/${id}/payment`, { amount })
  }
  ```
- **验证**: 调用后返回更新后的 Liability 对象，remaining_amount 减少

#### A3. 负债 store 添加还款方法
- **文件**: `frontend/src/stores/liability.ts`
- **改动**: 新增 `recordPayment` action，调用 API 并更新本地状态
- **验证**: store 中 liability 的 remaining_amount 正确更新

#### A4. 实现 Token 自动刷新
- **文件**: `frontend/src/api/index.ts`
- **改动**: 响应拦截器中，401 时先尝试 refresh token，成功则重试原请求
- **关键逻辑**:
  1. 检测 401 响应
  2. 如果有 refresh token，调用 `/auth/refresh` 获取新 access token
  3. 更新存储的 token
  4. 用新 token 重试原始请求
  5. 如果 refresh 也失败，才清除 auth 并跳转登录
  6. 使用锁机制防止并发刷新
- **验证**:
  - access token 过期后，操作不中断，自动续期
  - refresh token 也过期时，正确跳转登录页

#### A5. 负债还款 UI
- **文件**: `frontend/src/pages/LiabilityListPage.vue` 或新建 `LiabilityDetailPage.vue`
- **改动**:
  - 在负债卡片上添加"还款"按钮
  - 点击弹出 Vant Dialog 输入还款金额
  - 调用 store.recordPayment()
  - 成功后刷新列表，显示 Toast 提示
- **验证**:
  - 点击还款 → 输入金额 → 确认 → remaining_amount 减少
  - 还清时（remaining_amount = 0）负债自动标记为 inactive

#### A6. 负债详情页
- **文件**: 新建 `frontend/src/pages/LiabilityDetailPage.vue`
- **路由**: 添加 `/liabilities/:id` 路由
- **内容**:
  - 负债基本信息（名称、分类、机构、利率）
  - 还款进度条（remaining / original）
  - 月供信息
  - 关联资产（如有）
  - 还款按钮
  - 编辑/删除操作
- **验证**: 从列表页点击负债卡片 → 进入详情页 → 信息正确展示

### Phase B: 后端测试

#### B1. 搭建测试框架
- **文件**: 新建 `backend/tests/conftest.py`
- **内容**:
  - 测试用 SQLite 内存数据库
  - FastAPI TestClient fixture
  - 注册/登录 helper fixture（获取 token）
  - 数据库 session fixture（每个测试自动回滚）
- **验证**: `pytest --co` 能发现测试

#### B2. 认证 API 测试
- **文件**: 新建 `backend/tests/test_auth.py`
- **测试用例**:
  - 注册成功 → 返回 token + 创建家庭
  - 重复用户名注册 → 400
  - 登录成功 → 返回 access + refresh token
  - 错误密码登录 → 401
  - Token 刷新 → 新 access token
  - 邀请码加入家庭 → 成功
  - 无效邀请码 → 404
  - 获取当前用户 → 返回用户信息
- **验证**: `pytest tests/test_auth.py` 全部通过

#### B3. 资产 API 测试
- **文件**: 新建 `backend/tests/test_assets.py`
- **测试用例**:
  - 创建资产（实物 + 金融）→ 201
  - 列表查询 + 筛选（按分类、类型、状态）
  - 更新资产 → 字段正确更新
  - 归档资产 → is_archived = True
  - 快速更新价值 → current_value 更新
  - 日耗计算正确性（purchase_price + maintenance / days）
  - 收益率计算正确性
  - 跨家庭隔离 → 403/404
- **验证**: `pytest tests/test_assets.py` 全部通过

#### B4. 负债 API 测试
- **文件**: 新建 `backend/tests/test_liabilities.py`
- **测试用例**:
  - 创建负债 → 201
  - 列表查询
  - 更新负债
  - 记录还款 → remaining_amount 减少
  - 还清 → is_active = False
  - 删除负债
- **验证**: `pytest tests/test_liabilities.py` 全部通过

#### B5. 仪表盘 API 测试
- **文件**: 新建 `backend/tests/test_dashboard.py`
- **测试用例**:
  - overview → 总资产/总负债/净资产正确
  - allocation → 分类占比之和 = 100%
  - daily-cost-ranking → 按日耗降序
  - low-usage-assets → 只返回 rarely/idle
  - investment-returns → 只返回金融资产，收益率正确
- **验证**: `pytest tests/test_dashboard.py` 全部通过

### Phase C: 构建与部署验证

#### C1. 前端构建验证
- **命令**: `cd frontend && npm run build`
- **验证**: 无 TypeScript 错误，dist/ 目录生成成功

#### C2. 后端启动验证
- **命令**: `cd backend && python -c "from app.main import app; print('OK')"`
- **验证**: 无 import 错误，app 对象创建成功

#### C3. Alembic 初始迁移
- **命令**:
  ```bash
  cd backend
  alembic revision --autogenerate -m "initial schema"
  alembic upgrade head
  ```
- **验证**: 迁移文件生成，数据库表创建成功

#### C4. Docker 端到端验证
- **命令**: `docker-compose up -d --build`
- **验证**:
  - 三个容器均为 healthy/running
  - `curl http://localhost:8080/api/health` → `{"status":"ok"}`
  - 浏览器访问 `http://localhost:8080` → 显示登录页
  - 注册 → 登录 → 添加资产 → 查看仪表盘 → 全流程通过

### Phase D: 集成验证场景

#### D1. 完整用户旅程测试
1. 注册账号"张三"，创建家庭"张家"
2. 添加实物资产：朝阳区房产（🏠，¥3,000,000，日耗相关字段填写）
3. 添加金融资产：招商银行存款（🏦，¥200,000，利率 2.5%）
4. 添加负债：房贷（mortgage，¥2,000,000，月供 ¥12,000）
5. 查看仪表盘：
   - 净资产 = 3,000,000 + 200,000 - 2,000,000 = ¥1,200,000 ✓
   - 资产配置饼图显示房产和存款 ✓
   - 日耗排行显示房产 ✓
   - 投资收益排行显示存款 ✓
6. 记录房贷还款 ¥12,000 → remaining 减少
7. 获取邀请码，用"李四"账号加入家庭
8. 李四添加资产，查看家庭汇总 → 包含两人资产

#### D2. 安全验证
1. 未登录访问 `/api/v1/assets` → 401
2. 李四访问张三的资产详情 → 同家庭可见
3. 创建新家庭"王家"，王五无法看到张家数据

#### D3. Token 刷新验证
1. 登录获取 token
2. 等待 access token 过期（或手动设置短过期时间测试）
3. 发起 API 请求 → 自动刷新 → 请求成功
4. refresh token 也过期 → 跳转登录页

---

## 四、优先级与工作量估算

| 编号 | 任务 | 优先级 | 复杂度 |
|------|------|--------|--------|
| A1 | 修复 PATCH → PUT | P0 | 1行改动 |
| A2 | 添加还款 API 方法 | P0 | 5行代码 |
| A3 | Store 添加还款方法 | P0 | 15行代码 |
| A4 | Token 自动刷新 | P0 | ~50行代码 |
| A5 | 还款 UI | P0 | ~40行代码 |
| A6 | 负债详情页 | P1 | ~150行代码 |
| B1-B5 | 后端测试 | P1 | ~400行代码 |
| C1-C2 | 构建验证 | P1 | 命令执行 |
| C3 | Alembic 迁移 | P2 | 命令执行 |
| C4 | Docker 验证 | P2 | 命令执行 |
| D1-D3 | 集成验证 | P1 | 手动测试 |

---

## 五、验收标准

全部完成后，系统应满足：

1. **功能完整**: 所有 MVP 功能可用，无 405/500 错误
2. **Token 续期**: 用户正常使用不会被意外登出
3. **还款流程**: 负债可记录还款，还清自动标记
4. **测试覆盖**: 后端核心 API 有自动化测试，`pytest` 全部通过
5. **可构建**: `npm run build` 和 `docker-compose up` 均成功
6. **安全隔离**: 跨家庭数据不可访问
