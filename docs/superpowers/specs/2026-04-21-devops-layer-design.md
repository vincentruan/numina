# DevOps Layer Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** 编码规范、Git工作流、测试规范、可观测性、定时任务

---

## Problem

1. 代码风格不一致，缺乏统一编码规范文档
2. Git 工作流程缺乏规范，分支命名混乱、commit message 不统一
3. 测试缺乏统一规范，测试数据污染生产环境
4. 系统缺乏操作历史记录和资产状态快照
5. 定时任务调度缺乏文档

---

## Goals

1. 确保代码风格一致性（双栈规范）
2. 规范分支命名和 commit message 格式
3. 定义统一测试账号和数据范围
4. 记录关键操作历史和净资产快照
5. 定义定时任务调度配置

---

## Architecture

### 双栈编码规范

**前端栈**：Vue 3 + TypeScript + Vite + Vant 4
**后端栈**：FastAPI + SQLAlchemy + Python 3.11

规范文档位于 `backend/CLAUDE.md` 和 `frontend/CLAUDE.md`。

### 分支策略

采用简化的 GitHub Flow：

```
main (稳定版本)
  ├── feature/* (功能开发)
  ├── fix/* (问题修复)
  └── hotfix/* (紧急修复)
```

### 测试分类

| 测试类型 | 位置 | 运行方式 |
|----------|------|----------|
| 后端单元测试 | `backend/tests/` | pytest |
| E2E 验收测试 | `tests/e2e/` | Shell 脚本 |
| 截图测试 | `tests/tools/screenshot/` | Puppeteer |

### 双层记录机制

**Activity 日志**：记录用户操作（create/update/delete/sell/retire/payment）
**Snapshot 快照**：记录系统状态（总资产/总负债/净资产）

---

## Implementation Details

### 前端编码规范

**Vue 3 Composition API**：
```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Asset } from '@/types'

const assets = ref<Asset[]>([])
const totalValue = computed(() => assets.value.reduce((sum, a) => sum + a.current_value, 0))
</script>
```

**命名约定**：

| 元素 | 命名规则 | 示例 |
|------|----------|------|
| 页面组件 | PascalCase + Page | `AssetListPage.vue` |
| 业务组件 | PascalCase | `AssetCard.vue` |
| 组合式函数 | camelCase + use | `useExchangeRate.ts` |
| Pinia Store | camelCase + use + Store | `useAssetStore.ts` |

### 后端编码规范

**FastAPI + SQLAlchemy**：
```python
class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
```

**路由组织**：
```python
router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("/")
def list_assets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return AssetService.list_assets(user.family_id, db)
```

### 分支命名规范

| 分支类型 | 命名格式 | 示例 |
|----------|----------|------|
| 功能开发 | `feature/<description>` | `feature/multi-currency` |
| 问题修复 | `fix/<issue-number>-<description>` | `fix/123-login-validation` |
| 紧急修复 | `hotfix/<description>` | `hotfix/security-patch` |

### Commit Message 格式

采用约定式提交：
```
<type>: <subject>

<body>

<footer>
```

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复问题 |
| docs | 文档更新 |
| refactor | 重构代码 |
| test | 测试相关 |
| chore | 其他修改 |

Subject 要求：
- 使用中文
- 不超过 50 字符
- 首字母大写

### 统一测试账号

| 字段 | 值 |
|------|-----|
| 用户名 | `demouser` |
| 密码 | `DemoPass123` |
| 家庭名 | `Demo Family` |

### 测试数据范围

| 类型 | 数量 | 覆盖范围 |
|------|------|----------|
| 实物资产 | 19 项 | 全部 13 个实物分类 |
| 金融资产 | 11 项 | 全部 8 个金融分类 |
| 负债 | 3 项 | 房贷、车贷、信用卡 |
| 心愿 | 5 项 | 不同优先级和状态 |
| 总资产价值 | ¥50,792,000 | — |
| 净资产 | ¥45,312,000 | — |

### Activity 日志触发时机

| 操作类型 | 实体类型 | 触发时机 |
|----------|----------|----------|
| create | asset | 资产创建 |
| update | asset | 资产更新（价值变更） |
| sell | asset | 资产出售 |
| retire | asset | 资产退役 |
| payment | liability | 负债还款 |

### Snapshot 快照触发方式

| 方式 | 触发时机 |
|------|----------|
| 手动 | 用户点击"生成快照" |
| 自动 | 每日 00:00 定时任务 |

### 定时任务调度

使用 APScheduler 实现：

| 任务 | 触发时间 | 说明 |
|------|----------|------|
| 汇率更新 | 08:00-23:00 每2小时 | 调用汇率 API |
| 快照生成 | 每日 00:00 | 记录净资产快照 |

```python
scheduler = BackgroundScheduler()

# 汇率更新：每2小时，随机偏移
for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
    offset = random.randint(0, 15)
    scheduler.add_job(fetch_rates, 'cron', hour=hour, minute=offset)

# 快照生成：每日 00:00
scheduler.add_job(generate_snapshots, 'cron', hour=0, minute=0)

scheduler.start()
```

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 测试数据生成 | `tests/data/seed-data.sh` |
| E2E 测试 | `tests/e2e/` |
| 后端单元测试 | `backend/tests/` |
| Activity 模型 | `backend/app/models/activity.py` |
| Snapshot 模型 | `backend/app/models/snapshot.py` |
| 定时任务 | `backend/app/scheduler.py` |
| PR 模板 | `.github/PULL_REQUEST_TEMPLATE.md` |

---

## Related Specs

- **数据层设计**：`2026-04-21-data-layer-design.md` — Activity、Snapshot 实体
- **安全层设计**：`2026-04-21-security-layer-design.md` — 安全日志