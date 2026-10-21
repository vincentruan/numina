# Learning OS 全面优化设计

## Intent（意图）

Numina 学习OS 的知识图谱和 AI 导师底座已具备，但存在两个结构性缺陷阻碍"12岁前完成结构化知识体系"的目标：

1. **家长决策成本过高** — 家长要从 3,598 个知识点中手动挑选并派发任务，对非教育专业的家长来说几乎不可能
2. **审核瓶颈阻塞学习** — 所有学习成果必须等家长审核才能推进，家长不活跃时孩子的学习链断裂

本次优化将学习OS从"家长手动驱动"转变为"系统智能推荐 + AI 自动评估 + 家长异步监督"的模式，同时重构大人端交互使其聚焦学习场景。

## Goals & Non-Goals

### Goals

- **G1**: 系统根据孩子年龄 + 课标对标 + 知识链断点，自动生成推荐学习路径
- **G2**: 提供预设课程路径（年级/学期/学科级别），家长一键派发
- **G3**: 重构 BabyLearningPage 为纯学习场景的一级 Hub
- **G4**: 家长端 DNA 3D 知识图谱（Marble 风格，移动端 3D 交互）
- **G5**: AI 自动评估 + 家长异步监督双轨制（AI 未启用时全部走家长审核）
- **G6**: 儿童端标签标注（区分系统推荐/家长派发/自己探索）
- **G7**: 复习闭环 — 儿童端 SM-2 复习提醒 UI
- **G8**: 审核拒绝后提供具体学习指导

### Non-Goals

- **N1**: 跨家庭同龄对标数据（自托管系统无外部统计数据，横向对标使用课标映射替代）
- **N2**: DNA 图谱 3D 引擎选型（参考 https://withmarble.com/curriculum 风格，引擎留给实现阶段；需先完成移动端原型验证 WebGL 性能可行性，不可行则降级为 2D 知识图谱）
- **N3**: 改变 BabyPage 的"家庭管理总览"定位（学习仍从 BabyPage 进入，BabyLearningPage 聚焦纯学习；BabyPage 内学习入口 cell 可提升视觉权重，但不改变 BabyPage 作为家庭管理总览的定位）

### Success Metrics

| Goal | 指标 | 目标 |
|------|------|------|
| G1 智能推荐 | 家长推荐接受率（确认派发 / 总推荐次数） | ≥ 60% |
| G2 预设路径 | 路径派发后完成率 | ≥ 50% |
| G3 Hub 重构 | 家长日均进入 BabyLearningPage 次数 | 较重构前提升 |
| G5 双轨审核 | 家长审核覆盖 AI 判定的比率 | ≤ 15% |
| G5 双轨审核 | 家长日均审核耗时 | 较优化前降低 ≥ 30% |
| G7 复习闭环 | 到期复习 topic 的 7 日内复习率 | ≥ 40% |

## Constraints

- **移动端优先**: 所有页面在 375×812 viewport 下完整可用
- **AI 可选**: AI 未启用时，所有功能降级为纯家长操作模式，不报错不阻塞
- **现有数据兼容**: 复用 os-taxonomy / os-taxonomy-beijing 的 curriculum_standards 映射，不新建数据集
- **增量迁移**: 现有 LearningAssignPage / BabyLearningPage / ChildLearningMapPage 渐进重构，不做 big-bang 替换

---

## Part 1: 智能推荐引擎

### 1.1 推荐逻辑

> **复用现有基础设施:** 推荐引擎扩展已有的 `zone_service.py`（当前提供 `get_zone_recommended_topic` 的 centrality 排序推荐），不新建独立 service 文件。新增断点遍历和课标缺口评分函数到同一文件中。

推荐引擎综合三个维度生成推荐路径：

**纵向（知识链断点）:**
- 遍历孩子已掌握的 topic，找到所有 `hard` 依赖边指向但未掌握的 topic
- 这些"卡点"是最高优先级推荐 — 不解决就无法继续前进

**横向（课标对标）:**
- 根据孩子年龄，从 curriculum_standards 中筛选该年龄段应掌握的课标条目
- 对比已掌握 topic 的 standards 覆盖，找出"同龄应会但未会"的知识点
- 按 `centrality`（图重要度）排序，优先推荐高 centrality 的

**时间（复习到期）:**
- `next_review_at ≤ now` 且 `mastery_level = mastered` 的 topic
-  spaced repetition 提醒，防止遗忘

**维度冲突解决（优先级从高到低）:**
1. 🔗 知识断点 — 阻塞后续学习，最高优先级
2. 📚 课标必会 — 同龄应会但未会
3. ⭐ 高基础度 — centrality 高但未阻塞
4. 🔄 需要复习 — SM-2 到期但已掌握

当同一 topic 同时命中多个维度时，合并标签并取最高优先级维度作为主排序键。

**输出:** 一条按优先级排序的 topic 列表，每个 topic 附带推荐原因标签。

### 1.2 推荐标签

| 标签 | 含义 | 颜色 |
|------|------|------|
| 🔗 知识断点 | 阻塞后续学习的前置缺失 | 红色 |
| 📚 课标必会 | 该年龄段课标要求掌握 | 橙色 |
| ⭐ 高基础度 | centrality 高，是多条路径的基础 | 蓝色 |
| 🔄 需要复习 | SM-2 到期复习 | 绿色 |
| 🎯 路径推荐 | 属于某条学习路径的下一站 | 紫色 |

### 1.3 推荐 API

新增后端端点（路由前缀 `/api/v1/family/learning/`，对应前端路由 `/baby/learning/`）：

```
GET /api/v1/family/learning/children/{child_id}/recommendations

Response:
{
  "path": {
    "name": "建议学习路径",
    "topics": [
      {
        "topic_id": "...",
        "topic_name": "分数加法",
        "reasons": ["知识断点", "课标必会"],
        "centrality": 0.85,
        "prerequisites_met": true,
        "suggested_position": 1
      }
    ],
    "total_count": 8
  }
}
```

### 1.3b 推荐模块交互状态

| 状态 | 触发条件 | 展示 |
|------|---------|------|
| **加载中** | 请求推荐 API 中 | 骨架屏 (skeleton) + "正在生成推荐路径…" |
| **空状态** | 知识图谱为空 / 孩子无学习历史 | "还没有学习数据，先去知识地图探索吧！" + 引导按钮 |
| **错误** | 网络失败 / API 异常 | "推荐暂时不可用，请稍后重试" + 重试按钮；不阻塞页面其他模块 |
| **成功** | 正常返回 | 推荐 topic 卡片列表 + 操作按钮 |

**换一批行为:** 点击 [换一批] 重新调用推荐 API，显示加载中骨架屏；之前已确认选中的 topic 保留不动。

**家长反馈:** 家长连续拒绝 3 次推荐时，系统记录拒绝原因标签（太难/太简单/不相关），用于后续推荐权重调整（实现阶段定义具体反馈存储结构）。

### 1.4 预设课程路径

基于 curriculum_standards 的 moe-2022-* 映射，按"年级+学期+学科"预生成标准路径。

```
预设路径示例:
├── 三年级上 · 数学 · 分数单元 (12 topics, 已按前置排序)
├── 三年级上 · 数学 · 乘除法单元 (15 topics)
├── 四年级上 · 语文 · 阅读理解 (10 topics)
└── ...
```

**数据来源:** 从 `curriculum_standards_json` 中提取 moe-2022 课标条目，按学科和 age_group 聚合，自动生成 topic 列表。后端提供种子脚本一次性生成，存入 `preset_learning_paths` 表。

**家长操作:** BabyLearningPage 显示"课程路径库"入口，家长按年级/学科筛选，一键派发给指定孩子。

**PresetPathsPage 交互:**
- 筛选器: 横向 chips（年级 → 学期 → 学科），分步选择
- 空结果: "该年级暂无预设路径"
- 路径卡片: 显示学科图标 + 路径名 + topic 数 + 已掌握进度
- 点击卡片: 展开 topic 列表预览 + [一键派发] 按钮

新增后端端点：

```
GET /api/v1/family/learning/preset-paths?grade=3&semester=fall&subject=mathematics
POST /api/v1/family/learning/preset-paths/{preset_id}/assign  { child_id }
```

---

## Part 2: BabyLearningPage 重构

### 2.1 页面定位

从当前的"信息聚合页"重构为**纯学习场景的一级 Hub**。所有与学习无关的内容（家务、心愿、盲盒等）留在 BabyPage。

### 2.2 孩子上下文继承

BabyPage 的孩子 tab 选中状态通过已有的 Pinia store (`useBabyStore`) 传递到 BabyLearningPage。学习相关的额外状态（如 `activePathId`）也扩展到此 store 中，不新建并行 store。

```
useBabyStore 扩展字段:
  selectedChildId: string | null    // 已有
  selectedChildName: string | null  // 已有
  activePathId: string | null       // 新增：当前选中/进行中的路径 ID

BabyPage: 选择"大宝" tab → useBabyStore.selectedChildId = dabao_id
         → 点击"学习管理" cell
         → 跳转到 BabyLearningPage

BabyLearningPage: onMounted → 读取 useBabyStore.selectedChildId
                 → 如果已有值，直接聚焦该孩子
                 → 如果没有，显示孩子选择器
```

**孩子切换时的刷新策略:** 切换孩子后，各模块独立 loading（骨架屏），不整页刷新；DNA 图谱模块因需重新加载 200-500 节点，显示独立 loading 遮罩。已加载的模块数据在后台刷新，期间显示旧数据 + "刷新中" 标记。

### 2.3 页面结构

**移动端模块策略:** 5 个模块按使用频率排序，高频模块（推荐、审核）默认展开；低频模块（课程路径库、进行中路径、图谱）默认折叠为摘要卡片，点击展开。审核区域标注为🔒家长专属。

```
BabyLearningPage
┌─────────────────────────────────────────┐
│ ← 学习管理          [孩子切换: 大宝|小宝] │
├─────────────────────────────────────────┤
│                                         │
│ 🌟 智能推荐路径                    [展开] │
│ ┌───────────────────────────────────┐   │
│ │ 系统为 大宝 推荐 8 个知识点         │   │
│ │ 基于: 2个知识断点 + 4个课标必会     │   │
│ │       + 2个待复习                  │   │
│ │                                   │   │
│ │ [🔗 分数加法] [📚 小数乘法]        │   │
│ │ [🔄 整数加减] ...                  │   │
│ │                                   │   │
│ │ [确认派发] [微调路径] [换一批]      │   │
│ └───────────────────────────────────┘   │
│                                         │
│ 📋 待审核 (3)                     🔒展开 │
│ ┌───────────────────────────────────┐   │
│ │ 大宝 · 分数减法 · 学习12分钟       │   │
│ │ [展开证据] → [通过] [要求重学]     │   │
│ │ ...                               │   │
│ │ [查看全部审核 →]                   │   │
│ └───────────────────────────────────┘   │
│                                         │
│ 📚 课程路径库                      [▶]  │  ← 默认折叠，显示摘要"3条可用路径"
│ 📍 进行中的路径                    [▶]  │  ← 默认折叠，显示摘要"三年级数学·分数 4/8"
│ 🧬 知识结构图谱                    [▶]  │  ← 默认折叠，显示缩略预览
│                                         │
└─────────────────────────────────────────┘
```

**审核区域权限:** 待审核模块仅家长可见（BabyLearningPage 为家长端页面，儿童端无此页面）。审核的"展开证据"在移动端使用底部弹出面板 (van-popup position=bottom)，展示 AI 评估详情：评分、薄弱点、建议重学知识点、推荐练习。

**"微调路径"交互:** 点击 [微调路径] 进入 RecommendationsPage，提供以下操作：
- **拖拽排序** — 长按 topic 卡片上下拖动调整顺序
- **移除 topic** — 左滑卡片显示 [移除] 按钮
- **替换 topic** — 点击 topic 卡片显示同维度替代 topic 列表（从推荐 API 的候补列表中获取）
- **添加 topic** — 底部 [从知识图谱添加] 按钮，跳转到 DNA 图谱选择

### 2.4 交互精简

| 变更 | 原因 |
|------|------|
| 审核只在 BabyLearningPage 操作 | 去重，不再在 LearningReviewsPage 重复 |
| LearningPathsPage 合并进 BabyLearningPage | 路径信息已在 Hub 展示，独立页面冗余 |
| LearningAssignPage 拆分 | 单个派发 → 从 RecommendationsPage / DNA 图谱发起；路径创建 → 从 PresetPathsPage 发起；原文件删除 |
| ChildLearningMapPage 升级为 DNA 图谱 | 替代当前列表视图，支持直接操作（嵌入式缩略预览 + 全屏独立页 `/baby/learning/:childId/map`） |
| 学习入口从 BabyPage summary cell 提升 | 更醒目的入口（仅提升 cell 视觉权重，不改变 BabyPage 家庭管理总览定位，符合 N3） |

---

## Part 3: DNA 3D 知识图谱

### 3.1 视觉设计

参考 Marble 的 curriculum visualization (https://withmarble.com/curriculum):

- **节点**: 每个点 = 一个 micro-topic，按学科着色
- **螺旋轴**: 沿年龄轴 (age_range) 螺旋上升排列
- **连线**: 前置依赖关系形成 thread，自然构成 DNA 双螺旋形态
- **掌握度叠加**:
  - 已掌握 (mastered): 亮色实心球 + 微光
  - 学习中 (learning): 脉动动画
  - 可用 (available): 半透明
  - 锁定 (locked): 暗色虚化
  - 需复习 (review): 黄色闪烁

### 3.2 移动端交互

- **手势**: 单指旋转、双指缩放、滑动沿轴移动
- **节点点击**: 弹出底部面板 (bottom sheet)，显示 topic 详情 + 操作按钮
- **图例**: 可折叠小条，点击展开颜色含义
- **学科过滤**: 顶部 chip 切换学科，过滤显示
- **操作按钮** (底部面板内):
  - "查看详情" → 展开 topic 完整信息
  - "添加到路径" → 加入当前推荐路径
  - "直接派发" → 创建单个任务
  - "查看前置" → 高亮显示前置依赖链

**全屏模式:** BabyLearningPage 内嵌图谱为缩略预览（约 200px 高），点击 [全屏] 进入 `/baby/learning/:childId/map` 独立页面。全屏页顶部有返回按钮 + 学科切换 chips，底部为操作面板。退出全屏返回 BabyLearningPage，保留之前的学科选择和缩放状态。

### 3.3 交互状态

| 状态 | 触发条件 | 展示 |
|------|---------|------|
| **加载中** | 加载 200-500 节点 + WebGL 初始化 | 骨架屏 + "正在加载知识图谱…" |
| **空状态** | 孩子无学习数据 / 当前学科无 topic | "还没有学习数据，先去探索知识吧！" + 引导按钮 |
| **WebGL 不可用** | 低端设备 / 浏览器不支持 WebGL | 降级为 2D 平面知识图谱（扩展现有 TopicGrid，增加掌握度颜色叠加和前置连线） |
| **错误** | 数据加载失败 | "知识图谱加载失败" + 重试按钮 |

### 3.4 性能考量

- 初始只加载当前学科的 topic（~200-500 节点），非全量 3,598
- 使用 LOD (Level of Detail): 远距离节点简化为点，近距离显示文字
- 连线使用 instanced rendering 减少 draw call
- 引擎选型留给实现阶段（Three.js / React Three Fiber / Babylon.js 等）

---

## Part 4: 审核双轨制

### 4.1 AI 启用时

```
学习完成 → AI 自动评估 → 结构化评分
  ├── score ≥ 阈值 → 自动通过 (completed_via: ai_assessment)
  │                  → 金币+XP奖励
  │                  → 解锁后续 topic
  │                  → 记入"已审核"列表供家长事后查看
  │
  ├── score < 阈值 → 建议重学
  │                  → 生成"薄弱点"反馈
  │                  → 不阻塞，但标记为需要关注
  │
  └── AI 服务异常 → 降级为家长审核 (parent_review 状态)
                    → 记录错误日志
                    → 不影响孩子当前学习进度
```

> **评估阈值:** 初始设为 `score ≥ 0.8` 自动通过。此阈值需要在实现阶段根据 AI 评估准确率调优——如果 AI 评估 false positive 率 > 10%，应提高阈值。建议上线后统计首月 AI 通过 vs 家长覆盖比率，目标覆盖比率 ≤ 15%。

**家长异步监督:**
- BabyLearningPage "审核"区域改为"学习动态"
- 展示最近的 AI 评估结果（通过/未通过）
- 家长可覆盖 AI 判定：将"已通过"降级为"需重学"，或将"未通过"升级为"已通过"
- 短时学习（<3分钟）的评估结果自动标记为"需关注"

**家长覆盖规则:** 覆盖操作记录 `overridden_by` (家长 ID)、`overridden_at` (时间戳)、`override_reason` (可选文本)。覆盖后的判定为最终判定。覆盖记录可在学习动态中查看，便于事后追溯。

**AI 错误累积防护:** 当连续 5 次 AI 评估结果被家长覆盖时，自动暂停 AI 自动通过功能，全部降级为家长审核，并通知家长"AI 评估可能需要调整"。家长可手动重新启用。

### 4.2 AI 未启用时

保持当前行为：所有学习成果进入 `parent_review` 状态，等待家长手动审核。无变化。

### 4.3 审核拒绝后的学习指导

当审核被拒绝（无论 AI 还是家长），系统生成具体反馈。

**家长端展示 (BabyLearningPage):** 审核区域直接展示薄弱点和重学建议。

**移动端审核证据面板:** 点击 [展开证据] 弹出底部面板 (van-popup position=bottom)，包含：
- AI 评分详情（评分维度、得分）
- 薄弱点分析
- 建议重学的知识点
- 推荐练习题（3 道同类型题目）
- 操作按钮: [通过] [要求重学] [覆盖为通过]

**儿童端反馈展示:** 见 Part 5.4 — TodayLearningCard、Topic 详情页、知识地图分别展示拒绝反馈。

```
┌─────────────────────────────────┐
│ 未通过 · 分数减法                │
│                                 │
│ 建议:                           │
│ • 薄弱点: 连续借位处理            │
│ • 建议重学: "借位减法" 知识点     │
│ • 推荐练习: 3道类似题目           │
│                                 │
│ [重新学习] [去练习场]             │
└─────────────────────────────────┘
```

后端在审核拒绝时，从 AI 评估 JSON 或家长反馈中提取薄弱维度，生成建议。

---

## Part 5: 儿童端配合

### 5.1 标签标注

在以下位置显示来源标签：

| 位置 | 标签样式 |
|------|---------|
| TodayLearningCard | `🌟 系统推荐` / `📝 爸妈布置` / `🔍 自己探索` |
| 知识地图 TopicGrid 节点 | 小角标：星(推荐)/书(派发)/镜(自选) |
| 学习路径卡片 | 路径头部：`🌟 智能推荐路径` / `📝 课程路径` |
| Topic 详情页面包屑 | 来源标签在面包屑右侧 |

### 5.2 复习提醒

TodayLearningCard 优先级更新：

```
pending_assignment > review_due > current_topic > recommended_topic > fallback
```

`review_due` 条件: `mastery_level = mastered` AND `next_review_at ≤ now`

知识地图上，到期复习的 topic 显示黄色"需复习"脉冲标记。

### 5.3 自学与派发的协调

- 孩子自选学习创建 `self_selected` assignment（已实现）
- BabyLearningPage 新增"自主探索"section，显示孩子的自学记录
- 自学 topic 如果 `centrality ≥ 0.7`，高亮告知家长"孩子主动学了重要知识点"
- 自学 topic 如果 `centrality < 0.7`，仍正常记录但不高亮；家长可在"自主探索"section 查看完整自学历史

**自学边界:** 孩子可以自由探索任何 `available` 状态的 topic（包括低 centrality 的），系统不强制限制。但如果孩子连续 3 次自学均为低 centrality topic，BabyLearningPage 向家长提示"孩子最近在探索非核心知识点，是否需要关注？"

### 5.4 审核拒绝后的儿童端展示

当审核被拒绝（AI 或家长），儿童端对应位置展示反馈：

| 位置 | 展示内容 |
|------|---------|
| TodayLearningCard | 状态标签变为 `❌ 需重学` + 薄弱点摘要 |
| Topic 详情页 | 顶部提示条：显示薄弱点 + [重新学习] [去练习场] 按钮 |
| 知识地图 | 被拒绝的 topic 节点显示红色虚线边框 + 感叹号图标 |

反馈内容来自 AI 评估 JSON 的薄弱维度字段（AI 审核时）或家长填写的反馈文本（家长审核时）。

---

## Part 6: 交互清理

### 6.1 页面路由变更

| 当前 | 优化后 | 说明 |
|------|--------|------|
| `/baby/learning` (BabyLearningPage) | 保持，重构内容 | 纯学习 Hub |
| `/baby/learning/assign` | 删除 | 单个派发 → RecommendationsPage / DNA 图谱；路径创建 → PresetPathsPage；原文件删除 |
| `/baby/learning/reviews` | 合并进 BabyLearningPage | 去重，Hub 内直接操作全部审核 |
| `/baby/learning/paths` | 合并进 BabyLearningPage | 路径信息在 Hub 展示 |
| `/baby/learning/:childId/map` | 升级为 DNA 图谱 | 替代列表视图 |

### 6.2 新增路由

| 路由 | 页面 | 说明 |
|------|------|------|
| `/baby/learning/preset-paths` | PresetPathsPage | 课程路径库（按年级/学科筛选） |
| `/baby/learning/recommendations` | RecommendationsPage | 智能推荐详情（微调 + 确认） |

### 6.2b AI 未启用时 BabyLearningPage 降级

当 AI 未启用时，BabyLearningPage 模块布局变化：

| 模块 | AI 启用时 | AI 未启用时 |
|------|----------|------------|
| 🌟 智能推荐路径 | AI 推荐 + 课标 + 断点 | 保留显示（推荐逻辑不依赖 AI，基于知识图谱遍历 + SM-2） |
| 📚 课程路径库 | 显示 | 显示（不依赖 AI） |
| 📋 待审核 | 显示 AI 评估结果 + 家长覆盖 | 显示家长手动审核队列（仅家长审核模式） |
| 📍 进行中的路径 | 显示 | 显示（不依赖 AI） |
| 🧬 知识结构图谱 | 3D/2D 图谱 | 显示（不依赖 AI） |

> 推荐引擎基于知识图谱遍历和 SM-2 复习周期计算，不依赖 AI 服务。因此 AI 未启用时仅审核模块从"AI 自动评估 + 家长监督"降级为"纯家长手动审核"，其余模块不变。

### 6.3 共享状态

扩展已有的 `useBabyStore`（见 Part 2.2），新增 `activePathId` 字段。不新建并行 store，避免与 `useBabyStore.selectedChildId` 重复。

BabyPage 的孩子 tab 切换时写入；BabyLearningPage 及所有子页面读取。

---

## What's Left to the Builder

以下决策留给实现阶段：

1. **DNA 3D 引擎选型** — Three.js / React Three Fiber / Babylon.js / 自定义 WebGL，需根据 Vue 3 兼容性和移动端性能实测决定；**如 WebGL 不可行，按 Part 3.3 降级为 2D 平面图谱**
2. **推荐算法权重调优** — 三个维度（断点/课标/复习）的优先级已在 Part 1.1 定义初始规则，需实测调整权重参数；定义"好推荐"的验收测试集
3. **预设课程路径的具体内容** — 需要审核 moe-2022 课标映射的准确性（自托管场景可由家长自行验证）
4. **AI 评估阈值调优** — 初始 0.8 已在 Part 4.1 设定，上线后根据 AI 通过 vs 家长覆盖比率调整（目标覆盖 ≤ 15%）
5. **DNA 图谱的性能优化策略** — LOD 阈值、instanced rendering 参数等需真机实测

---

## 文件索引（预计涉及的现有文件）

### 后端新增

- `server/apps/backend/app/services/learning/preset_path_service.py` — 预设课程路径
- `server/apps/backend/app/routers/learning_preset.py` — 预设路径 API
- `server/packages/db/models/learning/preset_path.py` — 预设路径模型
- Alembic migration: 新增 `preset_learning_paths` 表

### 后端修改

- `server/apps/backend/app/services/learning/zone_service.py` — 扩展推荐逻辑：新增 `find_breakpoint_topics()`（知识链断点遍历）+ 课标缺口评分
- `server/apps/backend/app/services/learning/progress_service.py` — 新增 `check_auto_pass()` 阈值检查 + 家长覆盖端点 + 覆盖记录 + AI 错误累积防护
- `server/apps/backend/app/services/learning/session_service.py` — AI 评估异常时降级为 `parent_review` 状态
- `server/apps/backend/app/routers/learning_family.py` — 新增推荐端点（复用 zone_service）+ 预设路径端点
- `server/apps/backend/app/routers/learning_child.py` — review_due 优先级

### 前端新增

- `frontend/apps/main/src/views/baby/learning/PresetPathsPage.vue` — 课程路径库
- `frontend/apps/main/src/views/baby/learning/RecommendationsPage.vue` — 智能推荐详情（微调 + 确认）
- `frontend/apps/main/src/composables/useLearningDnaGraph.ts` — DNA 图谱 composable
- `frontend/apps/main/src/components/learning/DnaGraph3D.vue` — 3D/2D 图谱组件（含 WebGL 降级）
- `frontend/apps/child/src/components/learning/SourceTag.vue` — 来源标签组件

### 前端修改

- `frontend/apps/main/src/stores/baby.ts` — useBabyStore 扩展 `activePathId` 字段
- `frontend/apps/main/src/views/baby/BabyPage.vue` — 学习入口 cell 视觉权重提升
- `frontend/apps/main/src/views/baby/learning/BabyLearningPage.vue` — 重构为纯学习 Hub（模块折叠 + AI 降级）
- `frontend/apps/main/src/views/baby/learning/ChildLearningMapPage.vue` — 升级为 DNA 图谱（嵌入式预览 + 全屏独立页）
- `frontend/apps/main/src/views/baby/learning/LearningAssignPage.vue` — 删除（功能拆分至 RecommendationsPage / PresetPathsPage / DNA 图谱）
- `frontend/apps/main/src/views/baby/learning/LearningReviewsPage.vue` — 合并进 BabyLearningPage
- `frontend/apps/main/src/views/baby/learning/LearningPathsPage.vue` — 合并进 BabyLearningPage
- `frontend/apps/child/src/views/learning/LearningMapPage.vue` — 增加来源标签 + 复习到期脉冲标记 + 拒绝反馈标记
- `frontend/apps/child/src/components/learning/TodayLearningCard.vue` — 增加 review_due 优先级 + 来源标签 + 拒绝反馈展示
- `frontend/apps/child/src/api/learning.ts` — 新增推荐 API 调用
