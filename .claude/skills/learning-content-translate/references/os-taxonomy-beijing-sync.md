# Beijing Taxonomy Sync (os-taxonomy-beijing)

## Data Source

Beijing taxonomy: `https://github.com/luw2007/os-taxonomy-beijing.git`
Data clone: `server/data/os-taxonomy-beijing/` (independent clone, not a submodule —
managed by `scripts/sync-beijing-taxonomy.py`).

与上游 `os-taxonomy`（English only，submodule）不同，Beijing 数据集是**已翻译的中文数据**：
全部 1,590 个上游微主题已译为中文（复用上游 `mt_` ID），另含 2,008 个中国特有微主题
（`mtc_` 前缀，语文/道法/历史等）与中国教育部 2022 版课标对齐。
**因此加载北京数据不需要 LLM 翻译步骤。**

## Data Location

```
server/data/os-taxonomy-beijing/          ← 独立 git clone（非 submodule）
└── data/
    ├── topics.zh.json                 上游 1,590 个微主题的中文翻译（只含翻译字段，结构字段仍在上游 topics.json）
    ├── cn-topics.json                 2,008 个中国特有微主题（mtc_ 前缀）
    ├── dependencies.zh.json           3,221 条上游依赖边（中文说明）
    ├── cn-dependencies.json           2,619 条中国特有依赖（带 reviewStatus: reviewed/machine/rejected）
    ├── cn-bridge-dependencies.json    上游 mt_ 与 mtc_ 之间的桥接依赖
    ├── clusters.zh.json               183 个领域聚类的中文摘要
    ├── cn-curriculum-standards.json   中国教育部课标编号（codes-only）
    └── manifest.json                  计数 + SHA-256 校验和
```

共 9 个 JSON 文件（README 中列 8 个 + manifest）。`dimensions.json` / `domains.zh.json` /
`glossary.json` / `terminology.json` 为辅助参考数据。

## Update Workflow

### 1. 拉取最新数据

```bash
# 方式 A（推荐）：helper 脚本 — pull + 打印 commit + 打印后续步骤
python .claude/skills/learning-content-translate/scripts/sync-beijing-taxonomy.py

# 方式 B：手动
cd server/data/os-taxonomy-beijing && git pull
```

若 `server/data/os-taxonomy-beijing` 尚未 clone：

```bash
cd server/data
git clone https://github.com/luw2007/os-taxonomy-beijing.git os-taxonomy-beijing
```

### 2. 去重管道（dedup pipeline）

将 Beijing 数据并入本地 package 前，先跑 dedup 消除与本地已有 topic 的重复：

```bash
cd server
uv run python -m os_taxonomy.dedup --source beijing --fallback
```

完成后人工审查生成的 `dedup_mapping.json`（映射了哪些 Beijing 条目被合并/保留）。

### 3. 重新 seed

```bash
cd server
uv run python scripts/seed_learning_topics.py --source beijing \
  --data-dir server/data/os-taxonomy-beijing/data
```

## Key Differences from os-taxonomy (upstream)

| | os-taxonomy (upstream) | os-taxonomy-beijing |
|---|---|---|
| 语言 | English only | 预翻译中文（zh-CN） |
| 翻译步骤 | 需要 LLM 翻译 (`translate-to-package.py`) | **不需要** — 直接用 |
| 管理方式 | git submodule (`references/os-taxonomy/`) | 独立 clone (`server/data/os-taxonomy-beijing/`) |
| 中国特有内容 | 无 | `mtc_` 前缀 topics（语文/道法/历史） |
| 课标 | 英美 (NGSS/Common Core) | 中国教育部 2022 版 (`moe-2022-*` codes) |
| 桥接依赖 | 无 | `cn-bridge-dependencies.json`（mt_ ↔ mtc_） |
| 审核元数据 | 无 | `reviewStatus`（reviewed/machine/rejected）、`translationStatus` |
| dedup | N/A | 需要（Beijing topics 与本地 package 有重叠） |

## Caveats

- 成熟度 alpha：全部中文文本为机器翻译（仅 4 条人工校对）；`machine` 依赖边
  **不进入儿童路径**，`rejected` 边隐藏。`AI 复审 ≠ 教师人工审核`。
- `cnStandards` / 课标编号是**项目自建映射标识符**，非教育部官方代码（见上游
  `PROVENANCE.md`）。
- `topics.zh.json` 只含翻译字段 — 结构字段（`type`/`subject`/`domain`/`ageRange`）
  仍需上游 `os-taxonomy` 通过 `mt_` ID 关联。
