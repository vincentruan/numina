# Numina 测试规范

## 统一测试账号

所有测试脚本统一使用以下账号：

| 字段 | 值 |
|------|----|
| 用户名 | `demouser` |
| 密码 | `DemoPass123` |
| 显示名 | `Demo User` |
| 家庭名 | `Demo Family` |

账号由 `tests/data/seed-data.sh` 首次运行时自动创建（先尝试登录，失败则注册）。

---

## 测试环境要求

- 服务运行在 `http://localhost/`（通过 Docker Compose 启动）
- 已安装 `jq`（用于 JSON 解析）
- 截图测试需要 Node.js + Puppeteer

启动服务：

```bash
docker-compose up -d
```

---

## 测试数据生成

**位置：** `tests/data/seed-data.sh`

**运行：**

```bash
./tests/data/seed-data.sh
```

**生成内容：**

| 类型 | 数量 | 说明 |
|------|------|------|
| 实物资产 | 19 项 | 覆盖全部 13 个分类 |
| 金融资产 | 11 项 | 覆盖全部 8 个分类 |
| 负债 | 3 项 | 信用卡、贷款、其他 |
| 心愿 | 5 项 | 多优先级 |

**参考数据：**
- 总资产：¥50,792,000
- 总负债：¥5,480,000
- 净资产：¥45,312,000

---

## E2E 测试

**位置：** `tests/e2e/`

| 脚本 | 说明 | 运行命令 |
|------|------|---------|
| `acceptance.sh` | 基础 API 验收测试（认证、资产、负债、心愿、仪表盘、家庭） | `./tests/e2e/acceptance.sh` |
| `extended.sh` | 扩展测试（CRUD、分类、标签、成员管理、快照） | `./tests/e2e/extended.sh` |
| `wishes-liabilities.sh` | 心愿和负债全字段专项测试 | `./tests/e2e/wishes-liabilities.sh` |

所有脚本均使用 `demouser` 账号，依赖 `jq` 处理 JSON 响应。

---

## 截图测试

**位置：** `tests/screenshot/capture.js`

**运行：**

```bash
cd tests/screenshot
npm install puppeteer   # 首次运行
node capture.js
```

**输出：** `tests/screenshot/screenshots/`（17 个页面截图）

**覆盖页面：** 登录、注册、加入家庭、仪表盘、资产列表/详情/表单、负债列表/详情、心愿列表、统计、家庭、设置、分类管理、标签管理

---

## 后端单元测试

**位置：** `backend/tests/`（36 个测试，使用内存 SQLite）

```bash
cd backend
uv run pytest tests/ -v
```

---

## 测试组织约定

- 仿真、E2E、集成、截图脚本 → `tests/`
- 后端单元测试 → `backend/tests/`
- 前端单元测试（如有）→ `frontend/tests/`
