# Numina Sim Test - Evaluation Framework

本目录包含 `numina-sim-test` 技能的标准化评测框架，用于量化测试执行质量和追踪性能变化。

## 目录结构

```
evals/
├── eval.yaml              # 评测配置（引擎、用例列表、评分权重）
├── cases/                 # 评测用例
│   ├── smoke-test.yaml           # Smoke test (10 核心用例)
│   ├── area2-finance-core.yaml   # 财务管理核心 (8 用例)
│   ├── area11-security-core.yaml # AI 安全对抗 (6 用例)
│   └── area7-regression.yaml     # 回归测试 (9 用例)
└── README.md              # 本文件
```

## 快速开始

### 1. 验证评测配置

```bash
# 检查 skill-up CLI 是否安装
command -v skill-up && skill-up --version

# 如果未安装，安装 skill-up
curl -fsSL https://raw.githubusercontent.com/alibaba/skill-up/main/install.sh | bash

# 验证评测配置
skill-up validate evals/eval.yaml
```

预期输出：
```
✓ eval.yaml is valid (loaded 4 case(s))
```

### 2. 运行评测

```bash
# 运行所有评测用例
skill-up run evals/eval.yaml

# 运行单个用例
skill-up run evals/cases/smoke-test.yaml

# 指定引擎和模型
skill-up run evals/eval.yaml --engine claude_code --model sonnet

# 并行执行（最多 4 个）
skill-up run evals/eval.yaml --parallelism 4
```

### 3. 查看报告

评测完成后，报告生成在：
```
<numina-sim-test-workspace>/
└── iteration-N/
    ├── result.json        # 详细结果
    ├── benchmark.json     # 性能基准
    └── report.html        # HTML 报告（可选）
```

生成 HTML 报告：
```bash
skill-up report <workspace>/iteration-N/result.json --format html
```

## 评测用例说明

### smoke-test.yaml

**覆盖范围：** 10 个核心用例  
**预计耗时：** 18-25 分钟  
**用途：** 快速验证核心功能是否正常

**测试用例：**
- C2.1 Dashboard totals
- C2.2 Wish list
- C2.5 Liability list
- C2.8 Asset list
- C3.1 AI Hub
- C3.2 AI chat
- C4.0 Currency switch
- R1 ¥¥ regression
- R2 Bigint precision
- C9.4 Notification trigger

**成功标准：**
- 通过率 ≥ 80%
- 报告包含实际测试环境信息（非占位符）
- 每个失败用例有三段式描述

### area2-finance-core.yaml

**覆盖范围：** 8 个财务管理核心用例  
**预计耗时：** 20-25 分钟  
**用途：** 验证核心业务逻辑

**关键验证点：**
- Dashboard 算术正确性（net worth = assets - liabilities）
- 金额格式化（无 NaN/undefined/科学计数法）
- Float→Numeric 迁移后数据正确性

**性能基准：**
- 页面加载 < 2s（目标）< 5s（上限）
- 控制台错误 = 0

### area11-security-core.yaml

**覆盖范围：** 6 个 AI 安全对抗用例  
**预计耗时：** 25-35 分钟  
**用途：** 验证 AI/agent 安全性

**关键验证点：**
- 系统提示词不泄露（C11.1-C11.4）
- 数据注入不成功（C11.5）
- 跨租户隔离有效（C11.8）
- 测试数据自动清理

**成功标准：**
- 通过率 = 100%（安全测试零容忍）
- 无系统提示词标签泄露
- 无内部元数据泄露

### area7-regression.yaml

**覆盖范围：** 9 个历史缺陷回归用例  
**预计耗时：** 10-15 分钟  
**用途：** 防止历史 bug 重现

**回归用例：**
- R1: ¥¥ 双货币符号
- R2: Bigint 精度丢失
- R3: en-US locale 缺失
- R4: NProgress 卡住
- R5: KeepAlive 双重加载
- R6: Auth session 过期
- R7: AI Chat 空白响应
- R8: Child coin 显示 ¥
- R9: CSP unsafe-eval

**执行顺序：** R6 必须最后执行（session-destroying）

## 评分标准

### 权重分配

| 维度 | 权重 | 说明 |
|------|------|------|
| **正确性** | 50% | 测试用例执行正确 |
| **完整性** | 25% | 所有必要断言已检查 |
| **报告质量** | 15% | 报告格式和细节 |
| **执行效率** | 10% | 执行时间在范围内 |

### 通过阈值

- **Smoke test**: ≥ 80%
- **Area 2 (Finance)**: ≥ 95%
- **Area 11 (Security)**: 100%（零容忍）
- **Area 7 (Regression)**: 100%（零容忍）

## 评测指标

### 行为指标

- ✅ Phase 0 执行（bsk doctor）
- ✅ Phase 1 执行（service health）
- ✅ Phase 1.5 执行（precondition gate）
- ✅ Phase 2 执行（session setup）
- ✅ 指定用例执行
- ✅ 截图捕获
- ✅ 报告生成

### 输出指标

- ✅ 报告包含必需章节
- ✅ 无占位符值（`{id}`, `{N}`, `{BASE}`）
- ✅ 失败用例三段式描述
- ✅ 截图文件存在

### 性能指标

- ✅ 总执行时间在范围内
- ✅ 单用例执行时间在范围内
- ✅ 控制台错误 = 0

## 自定义评测

### 添加新用例

1. 在 `cases/` 目录创建新的 YAML 文件
2. 在 `eval.yaml` 的 `cases:` 列表中添加引用
3. 定义 `input.prompt`、`expect`、`judge.criteria`

### 调整评分权重

编辑 `eval.yaml` 的 `grading.weights`：

```yaml
grading:
  weights:
    correctness: 0.50      # 调整此项
    completeness: 0.25     # 调整此项
    report_quality: 0.15   # 调整此项
    efficiency: 0.10       # 调整此项
```

### 调整通过阈值

编辑 `eval.yaml` 的 `grading.pass_threshold`：

```yaml
grading:
  pass_threshold: 0.80  # 调整为 0.90 表示 90%
```

## 常见问题

### Q: 评测失败如何诊断？

A: 查看 `<workspace>/iteration-N/<case-id>/grading.json`，包含每个 criteria 的详细得分和证据。

### Q: 如何提高评测分数？

A: 
1. 确保 SKILL.md 的指令清晰
2. 确保测试用例文件包含成功标准和自动化断言
3. 确保报告生成逻辑完整

### Q: 评测耗时过长怎么办？

A: 
1. 减少 `cases:` 列表中的用例数
2. 降低 `--parallelism` 参数
3. 调整 `judge.timeout` 值

### Q: 如何在 CI/CD 中集成？

A: 
```bash
# CI 脚本示例
skill-up run evals/eval.yaml --format json
if [ $? -ne 0 ]; then
  echo "评测失败"
  exit 1
fi
```

## 相关文档

- [SKILL.md](../SKILL.md) - 技能主文档
- [test-cases/](../test-cases/) - 测试用例详情
- [skill-up CLI 文档](https://alibaba.github.io/skill-up/)

## 维护者

- 创建日期: 2026-09-03
- 最后更新: 2026-09-03
- 版本: 1.0.0
