# 知识图谱数据质量报告 (os-taxonomy-beijing)

> **生成日期**: 2026-10-12
> **数据版本**: v1
> **数据源**: `server/packages/os_taxonomy/`

## 1. 总体统计

| 指标 | 数量 |
|------|------|
| 知识点 (topics) | 1590 |
| 先修关系 (dependencies) | 3221 |
| 聚类 (clusters) | 183 |
| 唯一 topic IDs | 1590 |
| 重复 ID | 0 |

## 2. 学科分布

| 学科 | 数量 | 占比 | 平均先修边 |
|------|------|------|-----------|
| Science | 547 | 34.4% | 2.0 |
| Mathematics | 503 | 31.6% | 2.1 |
| English | 286 | 18.0% | 2.1 |
| History | 90 | 5.7% | 2.4 |
| Personal & Social Development | 88 | 5.5% | 2.2 |
| Life Skills | 37 | 2.3% | 2.1 |
| Computing | 21 | 1.3% | 1.9 |
| Learning to Learn | 18 | 1.1% | 5.3 |

## 3. 知识点类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
| CONCEPTUAL | 810 | 50.9% |
| PROCEDURAL | 512 | 32.2% |
| META | 144 | 9.1% |
| LANGUAGE | 75 | 4.7% |
| REPRESENTATIONAL | 49 | 3.1% |

## 4. 孤立节点检测

**孤立节点数**: 0 (无入边且无出边)

✅ 无孤立节点。

## 5. 断链检测

**断链数**: 0 (引用不存在的 topic ID)

✅ 无断链。所有依赖引用的 topic ID 均存在。

## 6. 循环依赖检测

**环路数**: 0

✅ 无循环依赖。图谱为有向无环图 (DAG)。

## 7. 先修关系强度分布

| 强度 | 数量 | 占比 |
|------|------|------|
| hard | 2025 | 62.9% |
| soft | 1196 | 37.1% |

## 8. 年龄范围覆盖

| 学科 | 数量 | 最小年龄 | 最大年龄 | 缺年龄范围 |
|------|------|---------|---------|-----------|
| Computing | 21 | 5 | 11 | 0 |
| English | 286 | 4 | 14 | 0 |
| History | 90 | 5 | 14 | 0 |
| Learning to Learn | 18 | 5 | 11 | 0 |
| Life Skills | 37 | 5 | 11 | 0 |
| Mathematics | 503 | 4 | 15 | 0 |
| Personal & Social Development | 88 | 5 | 14 | 0 |
| Science | 547 | 5 | 14 | 0 |

## 9. 聚类覆盖率

- 聚类总数: 183
- 领域总数 (subject+domain): 54
- 有聚类的领域: 41
- 无聚类的领域: 13

**未覆盖领域**:

| 学科 | 领域 | 知识点数 |
|------|------|---------|
| History | Ancient Greece & Rome | 29 |
| Science | Polar Regions | 25 |
| History | Medieval Times | 25 |
| Science | Rainforests | 25 |
| Science | Insects & Minibeasts | 22 |
| Computing | Artificial Intelligence | 21 |
| Life Skills | Money & Finance | 20 |
| Learning to Learn | Learning to Learn | 18 |
| Life Skills | Entrepreneurship | 17 |
| Mathematics | Probability | 15 |
| History | Historical Thinking | 7 |
| Personal & Social Development | Self-Awareness | 7 |
| English | English Thinking | 7 |

## 10. 中文翻译覆盖率

| 字段 | 已翻译 | 翻译率 |
|------|--------|--------|
| nameZh | 1590 | 100.0% |
| descriptionZh | 1590 | 100.0% |
| evidenceZh | 1555 | 97.8% |
| assessmentPromptZh | 1590 | 100.0% |

## 11. 跨学科依赖分析

跨学科先修关系: 161 (5.0%)

示例:
- 岩层与地球历史 (Science) ← 三维立体图形（9岁及以上） (Mathematics)
- 推荐书籍 (English) ← 学习后反思 (Learning to Learn)
- 科学知识可以不断修正 (Science) ← 学习后反思 (Learning to Learn)
- 分类整理（6岁及以上） (Mathematics) ← 提问 (English)
- 理解分数（9岁及以上） (Mathematics) ← 从错误中学习 (Learning to Learn)

## 12. 总结与处理方案

### 数据质量评级

✅ **整体质量良好** — 无严重问题。

### 处理方案汇总

| 问题类型 | 处理方案 | 影响范围 |
|---------|---------|---------|
| 孤立节点 | 标记但不删除，保留完整性 | 仅影响图谱可视化 |
| 循环依赖 | 记录并在 progress_service 中添加防护 | 状态机需检测环路避免死锁 |
| 断链 | 在 topic_service 校验时过滤无效 prerequisite | 先修关系查询需做 null 检查 |
| 未覆盖领域 | Phase 7 扩展时优先补充 | 不影响当前 MVP |
