---
date: 2026-04-19
topic: tdd-optimization-multi-perspective
---

# TDD 优化：三视角并行审查

## Problem Frame

Numina 项目已从基础资产管理扩展为包含儿童财商教育、AI 智能建议、多存储后端、防爬虫安全等功能的完整家庭资产平台。但仿真测试 skill（`numina-sim-test`）和 E2E 测试脚本（`tests/data/seed-data.sh`、`tests/e2e/acceptance.sh`）未随功能迭代更新，导致：

1. **测试盲区**：9 个 AI 路由、家庭管理、金币系统、标签系统完全无单元测试
2. **仿真数据缺口**：seed 脚本未覆盖儿童系统（children、child_wishes、chores、coins、milestones、treasures）
3. **E2E 验收脚本**：未验证儿童工作流、AI 配置、多货币、文件同步等新功能
4. **截图覆盖不足**：capture.js 仅覆盖 17 个页面，缺少儿童视角页面、AI 功能页面

三个视角的关注点不同，需并行审查：

| 视角 | 核心关注 |
|------|---------|
| 父母视角 | 家庭资产管理流畅性、亲子互动体验、数据安全感 |
| 孩童视角 | 可玩性、财商培养、寓教于乐、成就感 |
| 工程师视角 | 数据隔离、并发安全、性能、健壮性 |

---

## Requirements

**仿真测试 Skill 更新（numina-sim-test）**

- R1. Skill 的「Seed Test Data」阶段脚本内容需补充儿童系统数据（路径 `tests/data/seed-data.sh` 已正确，需更新脚本内容）
- R2. Skill 的「API Acceptance Tests」阶段补充儿童系统端点验证：children CRUD、child_wishes 审批流、chores 完成流、coins 余额与赠送
- R3. Skill 的「Screenshot Capture」阶段扩展截图列表覆盖儿童视角页面（儿童登录、心愿列表、任务列表、金币余额、里程碑）；儿童页面需独立 PIN 登录 session，与父母 session 分开处理
- R4. Skill 的「UI/UX Audit」阶段增加「儿童财商」维度：可玩性、成就感视觉反馈、寓教于乐元素
- R5. Skill 的「UI/UX Audit」阶段增加「并发与性能」维度：乐观更新是否有竞态风险、加载骨架屏覆盖率

**Seed 数据脚本更新（tests/data/seed-data.sh）**

- R6. 补充创建至少 2 个 children（不同年龄段：幼儿 6 岁、青少年 14 岁）
- R7. 补充 child_wishes 数据：pending_review、active、realized、rejected 各状态至少 1 条
- R8. 补充 chores 数据：待完成、已完成待审批、已批准各状态至少 1 条
- R9. 补充 coins 交易记录：赚取（chore 完成）、消费（wish 实现）、赠送（sibling gift）
- R10. 补充 milestones 数据：至少 3 条里程碑（储蓄目标达成、第一笔投资、完成 10 个任务）
- R11. 补充 treasures 数据：至少 3 件宝藏（与资产关联）

**E2E 验收脚本更新（tests/e2e/acceptance.sh）**

- R12. 补充儿童 PIN 登录流程验证
- R13. 补充 child_wish 完整审批流：创建 → 父母设置金额 → 批准 → 实现
- R14. 补充 chore 完整流程：创建 → 儿童完成 → 父母审批 → 金币发放
- R15. 补充 coins 余额查询与赠送验证
- R16. 补充多货币资产创建与汇率换算验证
- R17. 补充家庭成员管理：邀请码生成、成员角色变更、成员移除

**后端单元测试补充（backend/tests/）**

- R18. 新增 `test_family.py`：家庭信息、成员管理、邀请码、标题自定义（当前无此测试文件）
- R19. 新增 `test_tags.py`：标签 CRUD、资产标签关联、跨家庭隔离（当前无此测试文件）
- R20. 扩展 `test_coin_gifting.py`：补充余额查询、ledger 分页、并发赠送场景（当前仅测试赠送基本流程）
- R21. 新增 `test_ai_config.py`：AI 提供商配置、API key 加密存储、连通性测试（mock LLM，当前 9 个 AI 路由无单元测试）

**三视角专项验证点**

- R22. 【父母视角】验证跨家庭数据隔离：家庭 A 的资产/负债/儿童数据对家庭 B 完全不可见
- R23. 【父母视角】验证儿童审批流的通知机制：child_wish 状态变更后父母端可感知
- R24. 【孩童视角】验证金币余额实时性：chore 审批后金币立即反映在余额中（无缓存延迟）
- R25. 【孩童视角】验证心愿进度可视化：child_wish 的 target_amount 与 coins 余额的进度比例正确
- R26. 【工程师视角】验证并发金币赠送不产生负余额：两个并发请求同时赠送超出余额时，至少一个应失败
- R27. 【工程师视角】验证 JWT payload 中 family_id 与数据库一致：token 中的 family_id 不可被篡改访问他人数据
- R28. 【工程师视角】验证文件同步 jitter 机制：多实例同时触发 sync 时不产生重复写入

---

## Success Criteria

- `uv run pytest tests/ -v` 全部通过，覆盖率从当前约 60% 提升至 80%+（按路由数量计）
- `./tests/data/seed-data.sh` 执行后，儿童系统数据完整（children、wishes、chores、coins、milestones、treasures 均有数据）
- `./tests/e2e/acceptance.sh` 覆盖儿童工作流，pass rate 100%
- `numina-sim-test` skill 截图覆盖儿童视角页面，UI 审计无 P0 问题
- 三视角审查中，R22–R28 专项验证点全部通过

---

## Scope Boundaries

- 不实现新功能，仅补充测试和仿真数据
- AI 路由测试仅 mock LLM 调用，不测试 AI 响应质量
- 不修改前端代码（除非 UI 审计发现 P0 问题）
- 不覆盖 WebDAV/GitHub 存储后端的集成测试（需 Docker 环境，标记为 `@pytest.mark.integration`）
- 性能基准测试（load testing）不在本次范围内

---

## Key Decisions

- **并行三视角**：R22–R28 专项验证点在仿真测试阶段由三个 Agent 并行审查，而非串行
- **Mock AI**：AI 路由测试使用 `unittest.mock` patch LLM 客户端，避免真实 API 调用
- **seed 脚本幂等性**：新增儿童数据时保持幂等（先查询再创建），与现有 seed 逻辑一致
- **截图扩展**：capture.js 新增儿童视角路由，需要儿童 PIN 登录的独立 session

---

## Dependencies / Assumptions

- 儿童系统路由（children、child_wishes、chores、coins）已实现且可用（已验证：backend/app/routers/ 中存在对应文件）
- `test_coin_gifting.py` 已存在，R20 在其基础上扩展
- 前端儿童视角页面已实现（待截图验证）

---

## Outstanding Questions

### Deferred to Planning

- [Affects R26][Technical] 并发金币赠送测试的实现方式需确认数据库事务隔离级别（SQLite WAL vs MySQL InnoDB），但测试本身必须实现——可先用 SQLite 验证乐观锁行为，MySQL/PostgreSQL 作为集成测试标记
- [Affects R28][Needs research] 文件同步 jitter 测试需要了解 `backend/app/` 中 scheduler 的具体实现机制再决定 mock 策略
- [Affects R3][Technical] 儿童视角截图需要确认前端路由路径（`/children/:id/wishes` 等）及 PIN 登录的 localStorage token 格式

## Next Steps

-> `/ce:plan` 制定分步实施计划，优先级：seed 数据 → E2E 脚本 → 单元测试 → skill 更新 → 三视角并行仿真
