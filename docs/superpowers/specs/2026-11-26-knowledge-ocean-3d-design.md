# 2026-11-26 KnowledgeOcean3D（T5–T10）设计

## 意图与原因

Issue #243 的 3D 知识海洋仍未实现。当前 SVG 地图是信息图，不是可探索的世界；T5–T10 要把它转成 3D 岛群场景：悬浮岛屿、动态海面、随掌握度变化的雾层、始终可读的标签，以及双击/捏合/返回的层级相机动画。

本次只交付 T5–T10 的 3D 场景核心。HUD 动效、岛屿点亮闭环、错误反馈、可访问性 DOM 列表、降级接线、截图回归与真机性能测试留待后续任务。

## 目标

- 在独立路由 `/learning/ocean-3d` 提供 3D 海洋；现有 `/learning` 与 `KnowledgeOcean.vue` 不变。
- 抽取一次共享 3D 框架，并让现有 3D 城堡改用该框架；城堡对外行为与测试保持兼容。
- 3D 内容做两级：L0 学科岛群、L1 某学科的领域分区；领域进入知识点层时复用现有 2D 交互。
- T5 渲染器/场景/相机/ResizeObserver/三路生命周期；T6 岛屿网格；T7 shader 海面；T8 雾层与掌握度环；T9 Sprite 标签；T10 anime.js 相机层级动画。

## 非目标（本次不做）

- 不修改 2D `LearningMapPage.vue`、`KnowledgeOcean.vue` 的数据与交互。
- 不做 T14 HUD 动效、T15 点亮闭环、T16 错误反馈、T18 可访问性 DOM 列表、T19 降级接线。
- 不做 T0.2/T0.5 真机数值补测、T20–T23 截图/内存回归验收。
- 不做完整三级 3D 星座；知识点层沿用现有 2D 页面/组件。
- 不新增音频文件或新依赖（three、rapier、animejs 已在依赖中）。

## 约束

- 单时钟：只有渲染循环调用 `tickDriver(now)`；所有相机/岛屿动画必须是 `animeDriver` 的子 timeline。
- 物理与视觉分离：若用 rapier 驱动岛屿起伏，body transform 与 visual group 分离；T5–T10 没有碰撞玩法，允许纯 shader/anime 起伏，不创建 body。
- 懒加载：`three` / `rapier` / anime 相关模块动态 import；既有 Vite `manualChunks` 保留。
- 三路生命周期：`onDeactivated` 与 `visibilitychange` 暂停；`onActivated` 恢复；`onBeforeUnmount` 完全 dispose。`webglcontextlost` 停循环并 emit fallback 事件，但本组件不渲染 2D fallback。
- 视觉：沿用 Clay 主题 token（如 `--ocean-sea-color`、`--color-brand-*`）；字体沿用应用现有字体体系，不引入新字体；最终样式需比 mockup 更圆润：更大圆角、柔和描边/阴影、轻量字重层次。
- 布局：L0 岛屿不重叠、约 15% 边距；L1 领域块间留水路；标签置于岛屿上方且不被雾层遮挡，屏幕空间恒定字号（`sizeAttenuation: false`）。

## 方案

### 已考虑的方案

1. **独立 ocean3d/ 模块，不动城堡**：最小 blast radius，但相机手势与生命周期重复。
2. **抽共享框架 + 改城堡（选择）**：把渲染器生命周期、orbit 相机与拾取助手放到共享层，海洋和城堡都使用；城堡 API/测试保持兼容。长期重复最少，代价是城堡需做一次受控回归。
3. **单文件大组件**：改动少但难维护，与 castle3d 现有模块划分不一致。

选择 2。它匹配用户对“抽共享框架 + 改城堡”的明确选择；通过保留 `castle3d/CameraController.ts` 的兼容 re-export 和现有公开 API 控制回归面。

### 实现形状

```text
frontend/apps/child/src/
├── components/learning/scene3d/          # 新增：共享框架
│   ├── useSceneLifecycle.ts              # renderer/scene/camera/loop/resize/pause/teardown
│   ├── OrbitCameraController.ts          # 通用 orbit + anime 过渡 + pinch
│   └── resolveThemeColor.ts              # CSS var → three color（替代城堡内私有实现）
├── components/learning/castle3d/         # 改为使用 scene3d
│   └── CameraController.ts               # 保留对外 API，内部委托共享控制器
└── components/learning/ocean3d/          # 新增：T5–T10
    ├── KnowledgeOcean3D.vue              # WebGL 检测、canvas、HUD 插槽/事件、生命周期
    ├── OceanSceneBuilder.ts              # T6 岛屿网格 + T8 雾层/掌握度环 + dispose
    ├── OceanWater.ts                     # T7 shader 海面
    ├── OceanLabels.ts                    # T9 Sprite 标签 + 深度排序
    ├── OceanCameraController.ts          # T10 双击下潜/捏合上升/返回浮出
    └── __tests__/                        # 纯逻辑单测（不依赖 GL）
```

页面与路由：

- `src/pages/learning/LearningOcean3DPage.vue`（新）：获取 `getMyLearningMapIndex()` + `getTopicIndex()`，按 `LearningMapPage.vue` 现有口径计算 `subjects` 与 `domains`，接 3D 组件；L1 点领域后进入现有知识点层（通过路由参数/现有 2D 组件）。
- `src/router/index.ts`：新增 `learning/ocean-3d` 路由，name `KnowledgeOcean3D`，放在现有 `learning/castle-3d` 附近。
- i18n：新增 `learning.ocean3d.*` 中英文键；复用 `learning.ocean.*` 中可复用文案。

数据契约沿用 `KnowledgeOcean.vue` 的 `OceanSubject` / `OceanDomain`：至少包含 `terrain`、`displayName`、`icon`、`topicCount`、`masteryRatio`。组件事件：`previewSubject`、`selectSubject`、`previewDomain`、`selectDomain`、`zoomOut`、`fallback`、`interacted`。

### 各部分决策

- **T5 骨架**：`useSceneLifecycle` 创建一个可组合 handle（而非混入），负责 canvas 尺寸、`WebGLRenderer`、PerspectiveCamera、`ResizeObserver`、rAF 单循环、`tickDriver`、pause/resume/destroy；组件只负责构造场景与事件。动态 `import('three')` 在 mount 内完成。
- **T6 岛屿网格**：调用现有 `layoutIslands()` 的归一化坐标，映射到世界平面 X/Z；半径按 `topicCount` 与布局半径映射；低面数 `CylinderGeometry`/`SphereGeometry` 组合成悬浮岛，PBR 材质 + `castShadow/receiveShadow`；阴影只在场景小范围开启，避免移动端过载。
- **T7 海面**：大平面 `PlaneGeometry` + `ShaderMaterial`；顶点着色器用 `sin/cos` 叠加波浪，片元用主题色与轻微高光。uniform 时间由渲染循环写入，不走 anime timeline（避免每帧生成 tween）。
- **T8 雾层 + 掌握度环**：雾层是覆盖岛屿上方的半透明网格/材质，opacity 使用 `1 - sqrt(masteryRatio)`（0 掌握 → 1，完全掌握 → 0）；掌握度环是岛屿周围的圆环（`RingGeometry`），角度或亮度反映掌握度。雾层 `depthWrite: false`，标签在雾层之上。
- **T9 Sprite 标签**：`SpriteMaterial({ sizeAttenuation: false })`，canvas texture 绘制图标+名称；每帧按相机距离做深度排序，确保近景标签盖住远景标签，且标签不会被雾层或海面挡住。
- **T10 相机层级动画**：共享 `OrbitCameraController` 提供 orbit、pan、pinch；`OceanCameraController` 提供 `diveTo(subject)`、`ascend()`、`reset()`，全部创建 animeDriver 子 timeline。双击岛屿下潜 L1，捏合上升 L0，返回按钮浮出。
- **城堡接入**：`castle3d/CameraController.ts` 改为从 `scene3d/OrbitCameraController.ts` re-export 或薄封装，保留 `CameraController`、`createPanoramaCamera`、`createTowerCamera`、`frameCastle` 名称和行为；`CastleSceneBuilder` 的主题色解析迁移到 `scene3d/resolveThemeColor.ts`，城堡测试不改断言。`CastlePanorama.vue` 只替换内部导入，不改 emits/defineExpose。

## Builder check 后的定稿决定

- **页面状态只在当前页内保存**：L0/L1 选择和领域选择用 Vue ref 保存，不做跨路由持久化；离开页面后不恢复。与 `LearningCastle3DPage.vue` 的 layer 模式一致。
- **L1 领域点击后在当前页面切到 2D 知识点层**：复用 `TopicConstellation.vue` 或等价的现有 2D 组件，不跳新路由；返回按钮回到 3D L1，捏合回到 L0。
- **新页面只做一次轻量数据加载**：`getMyLearningMapIndex()` + `getTopicIndex()`，按现有口径计算 subject/domain。实现基础 loading/error/empty 状态，不复刻 pull-to-refresh、进度重算或详情批量加载。
- **城堡相机公开 API 冻结**：`CameraController`、`createPanoramaCamera`、`createTowerCamera`、`frameCastle` 的名称、签名和 `animateTo()` 的 Promise 语义不变；共享控制器通过薄封装/re-export 接入，既有城堡测试不改断言。
- **`prefers-reduced-motion` 纳入本次最小门控**：海面波浪、岛屿浮动改为静态；相机层级动画改为瞬时定位。这是 R14 已有基础设施的接入，不是 T18 的可访问性 DOM 列表工作。

## 留待实现者决定（无需再问用户）

- 具体几何参数（岛屿高度、环厚度、海面网格密度）以 390/768px 可读性和低面数为准。
- `OceanLabels` 的 canvas texture 尺寸与文字缓存策略。
- 单测覆盖：布局坐标确定性、fog opacity 映射、相机层级动画入口、20 次构造/销毁无 timeline 泄漏（纯 JS 层）。

## 验收口径（本次范围内）

- `pnpm -C apps/child typecheck`、`pnpm -C apps/child test:run`、`pnpm -C apps/child lint` 通过；城堡既有测试全绿。
- 新页面可通过 `/learning/ocean-3d` 打开；无 WebGL 时不导入 three，emit fallback 且不白屏（降级显示由后续 T19 接线）。
- 未在真机或浏览器实测前，不得声称帧率/内存数值。
