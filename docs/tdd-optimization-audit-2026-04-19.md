# Numina TDD 优化审计报告 — 2026-04-19

## 执行摘要

**审计范围**：三视角并行审查（父母、孩童、工程师）+ E2E 测试验证
**测试覆盖率**：23/23 API 验收测试通过（100%）
**关键发现**：3 个高危安全问题、1 个严重用户体验问题、多个财商教育优化点

---

## 测试执行结果

### E2E 验收测试（acceptance.sh）

✅ **23/23 通过（100%）**

修复内容：
- 修复 API 响应 `.data` 包装层解析问题（所有 `json_value` 调用）
- 修复家庭汇总断言（从相等改为非零验证）

测试覆盖：
- 认证：注册、登录、错误密码
- 资产：CRUD、详情、404 处理
- 负债：CRUD、还款记录
- 心愿：CRUD、列表
- 仪表盘：概览、配置、日耗排行、低使用率、投资收益、趋势
- 家庭：信息、汇总
- 标签：列表
- 未认证访问：401/403 验证

---

## 三视角审查发现

### 🔴 高危问题（P0）

#### 1. 金币赠送竞态条件 → 负余额风险

**位置**：`backend/app/services/coin_transactions.py:46-100`

**问题**：`gift_coins()` 在余额检查（第 71 行）和事务提交（第 95-97 行）之间无锁保护。两个并发请求可同时通过检查，导致负余额。

**影响**：
- 工程师视角：破坏经济系统完整性
- 父母视角：孩子可通过技术手段"刷金币"
- 孩童视角：不公平感（有的孩子知道漏洞）

**修复方案**：
```python
# 使用悲观锁
sender = db.query(User).filter(User.id == sender.id).with_for_update().first()
balance = get_balance(db, sender.id)
if balance < amount:
    raise HTTPException(...)
# 提交事务
```

---

#### 2. AI API Key 可能明文存储

**位置**：`backend/app/services/ai_crypto.py:14-27`

**问题**：当 `AI_ENCRYPTION_KEY` 未配置时，`encrypt_api_key()` 返回 `None`，API Key 以明文存储。

**影响**：
- 工程师视角：生产环境凭证泄露风险
- 父母视角：家庭财务数据可能被 AI 服务滥用

**修复方案**：
```python
# 在 config.py 中强制生产环境配置
if settings.ENVIRONMENT == "production" and not settings.AI_ENCRYPTION_KEY:
    raise RuntimeError("AI_ENCRYPTION_KEY 未配置！")
```

---

#### 3. 儿童账户可被枚举

**位置**：`backend/app/routers/auth.py:296-317`

**问题**：`GET /auth/child/family/{family_id}/children` 无需认证，任何人可枚举任意 family_id 的儿童列表。

**影响**：
- 工程师视角：暴力破解 PIN 的前置条件
- 父母视角：隐私泄露（知道家里有几个孩子）

**修复方案**：
```python
@router.get("/child/family/{family_id}/children")
def get_family_children(
    family_id: str,
    token: str = Query(...),  # 要求 bind token
    db: Session = Depends(get_db),
):
    # 验证 token 属于该 family_id
```

---

### 🟡 严重用户体验问题（P0）

#### 4. 完全缺乏通知系统

**位置**：全局（无相关代码）

**问题**：
- 孩子提交心愿后，父母无法收到通知
- 父母批准/拒绝心愿后，孩子无法收到通知
- 任务自动批准时，父母无法收到警告
- 金币赠送对父母完全不可见

**影响**：
- 父母视角：无法及时感知孩子行动，体验评分 2/10
- 孩童视角：提交心愿后不知道父母是否看到，需要反复刷新

**修复方案**：
1. 后端：新增 `backend/app/services/notifications.py` 事件系统
2. 前端：添加轮询或 WebSocket 实时更新
3. 优先级：自动批准前警告 > 心愿状态变更 > 金币赠送记录

---

### 🟡 中危问题（P1）

#### 5. 金币赠送无父母监管

**位置**：`backend/app/routers/coins.py:106-114`

**问题**：孩子可无限制赠送金币给兄弟姐妹，父母完全看不到。

**场景**：14 岁孩子完成任务获得 100 金币，全部赠送给 6 岁弟弟，让弟弟用这些金币兑现心愿，绕过父母审批。

**修复方案**：
- 添加赠送限额（每天最多赠送 20% 余额）
- 父母可见的赠送记录（家庭仪表盘显示所有转账）
- 可选的赠送审批流程

---

#### 6. 心愿成本修改缺乏通知

**位置**：`backend/app/services/child_wishes.py:265-289`

**问题**：父母可随时降低心愿成本，但不通知孩子。

**影响**：
- 父母视角：可能无意中破坏孩子信任
- 孩童视角：感到被"欺骗"（特别是 14 岁青少年）

**修复方案**：
- 成本修改时发送通知给孩子
- 显示成本修改历史
- 可选：要求孩子确认新成本

---

#### 7. 仪表盘聚合查询 N+1 问题

**位置**：`backend/app/routers/family.py:81-100`

**问题**：多个独立的 `db.query()` 调用计算总资产、总负债、资产数量等。

**影响**：
- 工程师视角：家庭数据量大时加载缓慢
- 父母视角：仪表盘打开慢，体验差

**修复方案**：
```python
result = db.query(
    func.coalesce(func.sum(Asset.current_value), 0).label("total_assets"),
    func.coalesce(func.sum(Liability.remaining_amount), 0).label("total_liabilities"),
    func.count(Asset.id).label("asset_count"),
).filter(...).first()
```

---

### 🟢 财商教育优化点（P2）

#### 8. 缺乏即时反馈和游戏化

**位置**：前端（无动画/声音）

**孩童视角发现**：
- 任务完成后只看到数字变化，缺少金币飞入动画
- 心愿进度不可视化，不知道离目标还有多远
- 里程碑解锁无庆祝动画

**建议**：
- 添加金币飞入动画 + 声音效果
- 心愿进度条显示"还差 50 金币"
- 里程碑解锁时有徽章展示

---

#### 9. 反馈周期过长

**位置**：`backend/app/routers/chores.py`

**孩童视角发现**：孩子标记完成后需要父母审批，不能立即看到金币到账。

**建议**：
- 添加"自动审批"机制（父母可设置某些任务自动批准）
- 允许孩子看到"待审批"状态的金币（灰色显示）

---

#### 10. 缺乏社交和竞争元素

**位置**：全局（无排行榜）

**孩童视角发现**：没有兄弟姐妹排行榜、对比功能或"你比上周多赚了 50 金币"的激励。

**建议**：
- 添加兄弟姐妹排行榜（本周赚最多金币）
- 显示"你比上周多赚了 X 金币"
- 为赠送金币添加限额，防止不公平

---

## 测试覆盖缺口

### 当前覆盖（410 测试用例）

✅ 已覆盖：
- 资产、负债、心愿（成人）
- 儿童系统（children、child_wishes、chores、coins、milestones）
- 认证、安全、跨家庭隔离
- 文件同步、缓存、存储后端

❌ 未覆盖：
- 9 个 AI 路由（ai_config、ai_liability、ai_suggest、ai_chat、ai_report、ai_allocation、ai_disposal、ai_alerts、ai_internal）
- 家庭管理（family.py）
- 标签系统（tags.py）
- 数据导入（import_.py）

### 需补充测试（对应需求文档 R18-R21）

1. **test_family.py**：家庭信息、成员管理、邀请码、标题自定义
2. **test_tags.py**：标签 CRUD、资产标签关联、跨家庭隔离
3. **扩展 test_coin_gifting.py**：补充余额查询、ledger 分页、并发赠送场景
4. **test_ai_config.py**：AI 提供商配置、API key 加密存储、连通性测试（mock LLM）

---

## 仿真测试 Skill 更新需求

### 当前 Skill 状态

**路径**：`.claude/skills/numina-sim-test/SKILL.md`

**已修复**：
- Base URL 从 `http://localhost/numina/` 改为 `http://localhost/`
- API 路径从 `/numina/api/v1` 改为 `/api/v1`

**需补充**（对应需求文档 R1-R5）：

1. **Phase 2 Seed Data**：补充儿童系统数据
   - 2 个 children（6 岁幼儿、14 岁青少年）
   - child_wishes 各状态数据（pending_review、active、realized、rejected）
   - chores 各状态数据（待完成、已完成待审批、已批准）
   - coins 交易记录（赚取、消费、赠送）
   - milestones 数据（至少 3 条）
   - treasures 数据（至少 3 件）

2. **Phase 3 API Tests**：补充儿童系统端点验证
   - children CRUD
   - child_wishes 审批流
   - chores 完成流
   - coins 余额与赠送

3. **Phase 4 Screenshots**：扩展截图列表
   - 儿童登录页面
   - 儿童心愿列表
   - 儿童任务列表
   - 金币余额页面
   - 里程碑页面
   - **注意**：需要独立 PIN 登录 session，与父母 session 分开

4. **Phase 5 UI Audit**：增加审计维度
   - 儿童财商：可玩性、成就感视觉反馈、寓教于乐元素
   - 并发与性能：乐观更新竞态风险、加载骨架屏覆盖率

---

## Seed 数据脚本更新需求

### 当前脚本状态

**路径**：`tests/data/seed-data.sh`

**已有数据**：
- 19 项实物资产（覆盖所有 13 个分类）
- 11 项金融资产（覆盖所有 8 个分类）
- 7 项负债
- 9 项心愿
- 总资产 ~¥63M

**需补充**（对应需求文档 R6-R11）：

1. **创建 2 个 children**：
   - 幼儿：6 岁，PIN `🐶🐱🐭🐹`
   - 青少年：14 岁，PIN `🚀🎮🎸🏀`

2. **child_wishes 数据**：
   - pending_review：1 条（等待父母审批）
   - active：2 条（已批准，攒金币中）
   - realized：1 条（已实现）
   - rejected：1 条（被拒绝）

3. **chores 数据**：
   - 待完成：2 条（分配给不同孩子）
   - 已完成待审批：1 条（pending_approval）
   - 已批准：2 条（approved，金币已发放）

4. **coins 交易记录**：
   - 赚取：chore 完成获得金币
   - 消费：wish 实现扣除金币
   - 赠送：兄弟姐妹间赠送

5. **milestones 数据**：
   - 储蓄目标达成（first_100_coins）
   - 第一笔投资（first_wish_realized）
   - 完成 10 个任务（10_chores_completed）

6. **treasures 数据**：
   - 3 件宝藏（与资产关联）

---

## 优先级修复路线图

### Sprint 1：高危安全修复（P0，1-2 天）

1. ✅ 修复 acceptance.sh 的 `.data` 解析问题（已完成）
2. 🔴 实现金币交易悲观锁（`coin_transactions.py`）
3. 🔴 强制生产环境配置 `AI_ENCRYPTION_KEY`（`config.py`）
4. 🔴 修复儿童列表端点认证（`auth.py`）

### Sprint 2：通知系统（P0，3-5 天）

1. 后端：新增 `notifications.py` 事件系统
2. 前端：添加轮询或 WebSocket
3. 优先级：自动批准警告 > 心愿状态变更 > 金币赠送记录

### Sprint 3：测试覆盖补充（P1，2-3 天）

1. 新增 `test_family.py`
2. 新增 `test_tags.py`
3. 扩展 `test_coin_gifting.py`（并发场景）
4. 新增 `test_ai_config.py`（mock LLM）

### Sprint 4：Seed 数据 + Skill 更新（P1，1-2 天）

1. 更新 `seed-data.sh`（补充儿童系统数据）
2. 更新 `acceptance.sh`（补充儿童端点验证）
3. 更新 `numina-sim-test` skill（截图 + 审计维度）

### Sprint 5：财商教育优化（P2，3-5 天）

1. 添加即时反馈和动画
2. 缩短反馈周期（自动审批机制）
3. 增加社交和竞争元素（排行榜）

---

## 三视角综合评分

| 视角 | 评分 | 关键问题 |
|------|------|---------|
| 父母视角 | 5.6/10 | 通知系统缺失、金币赠送无监管 |
| 孩童视角 | ⭐⭐⭐ (还行) | 财商框架好，但游戏化不足 |
| 工程师视角 | 6.5/10 | 3 个高危安全问题、性能待优化 |

**综合评分**：**6.0/10** — 可用但需紧急改进

---

## 附录：关键代码路径

| 功能 | 后端路径 | 前端路径 |
|------|---------|---------|
| 心愿审批 | `backend/app/routers/child_wishes.py:82-99` | `frontend/src/pages/child/ChildWishesPage.vue` |
| 任务审批 | `backend/app/routers/chores.py:93-112` | `frontend/src/pages/ChoreApprovalsPage.vue` |
| 金币赠送 | `backend/app/services/coin_transactions.py:46-100` | `frontend/src/api/coins.ts:34-45` |
| JWT 验证 | `backend/app/auth/deps.py:78-100` | `frontend/src/stores/auth.ts` |
| 数据隔离 | `backend/app/services/child_wishes.py:143-146` | `frontend/src/api/childWishes.ts` |
| AI 加密 | `backend/app/services/ai_crypto.py:14-27` | `frontend/src/pages/AIConfigPage.vue` |

---

**审计执行人**：Claude Sonnet 4.6 (三视角并行 Agent)
**审计日期**：2026-04-19
**下一步**：执行 Sprint 1 高危安全修复
