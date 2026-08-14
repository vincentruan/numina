# Numina 测试套件

## 目录结构

```
tests/
├── e2e/                          # Playwright E2E 测试
│   ├── *.spec.ts                 # 测试用例（按功能命名）
│   ├── smoke_test.py             # Python 冒烟测试
│   └── scripts/                  # Shell 测试运行器
│       ├── acceptance.sh         #   API 验收测试
│       ├── extended.sh           #   扩展 API 测试
│       ├── run-regression.sh     #   (位于 tests/ 根) 一键回归
│       ├── multi-provider-sim-test.sh
│       ├── test-child-simulation.sh
│       └── wishes-liabilities.sh
│
├── visual/                       # 视觉回归测试
│   ├── visual.config.ts
│   ├── visual-check.config.ts
│   └── visual-check.spec.ts
│
├── lib/                          # TypeScript 共享工具
│   ├── auth.ts                   #   登录/token 辅助
│   ├── fixtures.ts               #   测试 fixtures
│   └── routes.ts                 #   路由常量
│
├── data/                         # Python 测试数据 & 种子
│   ├── factories/                #   工厂函数 (assets, users, wishes…)
│   ├── scenarios/                #   预置场景 (demo, full, empty…)
│   ├── seed_data.py              #   数据生成
│   └── seed-data.sh              #   Shell 入口
│
├── fixtures/                     # 静态测试夹具
│   └── openapi.snapshot.json     #   OpenAPI schema 快照
│
├── tools/                        # 独立测试工具
│   ├── screenshot/               #   Puppeteer 截图工具 (独立 npm)
│   └── page-agent/               #   Page Agent 配置
│
├── scripts/                      # 辅助脚本
│   └── update-openapi-snapshot.js
│
├── reports/                      # 测试审计报告（历史存档）
│   └── ui-audit-*.md
│
├── docs/                         # 测试文档
│   ├── TEST_SPEC.md
│   ├── TEST_DATA_SUMMARY.md
│   └── WISHES_LIABILITIES_TEST_SUMMARY.md
│
├── playwright.config.ts          # Playwright 主配置
├── tsconfig.json                 # TypeScript 配置
├── package.json                  # Playwright 依赖
└── run-regression.sh             # 一键回归测试入口
```

## 统一测试账号

所有测试脚本统一使用 `demouser` 账号：

- **用户名**: `demouser`
- **密码**: `DemoPass123`
- **家庭**: `Demo Family`

儿童角色：`testchild`

## 快速使用

### 一键回归

```bash
./tests/run-regression.sh           # 完整回归（Docker + 数据 + Playwright）
./tests/run-regression.sh --keep-up # 保留 Docker 环境用于调试
```

### Playwright E2E

```bash
cd tests
npx playwright test                 # 运行所有 spec
npx playwright test e2e/smoke.spec.ts  # 运行单个 spec
```

### 视觉回归

```bash
cd tests
npx playwright test --config visual/visual.config.ts
npx playwright test --config visual/visual-check.config.ts
```

### API Shell 测试

```bash
bash tests/e2e/scripts/acceptance.sh   # API 验收
bash tests/e2e/scripts/extended.sh     # 扩展 CRUD
```

### 截图工具

```bash
cd tests/tools/screenshot
npm install
node capture.js
```

## 维护说明

- E2E spec 放 `e2e/`，shell 运行器放 `e2e/scripts/`
- 截图产出（`.png`）已被 `.gitignore` 排除
- `reports/` 存放历史审计报告，新报告按需提交
- Python 测试数据使用 `data/factories/` 和 `data/scenarios/`
