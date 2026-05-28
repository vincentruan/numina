# Loading Animation 重设计方案：极坐标旋转流动

**日期：** 2026-05-28  
**状态：** 待落地  
**影响范围：** `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

---

## 背景

当前 `MusicWaveCanvas.vue` 实现的是"扩散波纹"效果：多条线从中心向外扩散、生命周期结束后消失并重生。视觉上像水波，不够紧凑，且与页面切换语义（过渡、等待）的匹配感弱。

新方向：**5–9 条极坐标闭合曲线，锁定在圆形区域内，持续做有机旋转流动变形**，参考 TikTok logo 的液态流动感。

效果已通过 `loading-demo.html` 验证。

---

## 1. 技术方案

### 1.1 极坐标曲线模型

每条线是一条极坐标闭合曲线，半径由多个正弦谐波叠加：

```
r(θ, t) = R_base + A1·sin(n1·θ + drift1·t)
                 + A2·sin(n2·θ − drift2·t + φ2)
                 + A3·cos(n3·θ + drift3·t)
```

- `R_base`：基准半径（相对于 canvas 短边，约 0.44），每条线略有差异（±0.06），使线条分布在不同圆周层次上
- `n1, n2, n3`：谐波频率（整数），决定曲线"花瓣"数量，每条线取不同值（2–5），保证视觉多样性
- `A1, A2, A3`：各谐波振幅（相对于 R），控制扭曲剧烈程度
- `drift1, drift2, drift3`：各谐波相位随时间漂移速率，不同速率使曲线持续有机变形

转换为笛卡尔坐标时，整条曲线整体旋转角度 `rotation = t · rotSpeed + basePhase`：

```
x = cx + r(θ) · cos(θ + rotation)
y = cy + r(θ) · sin(θ + rotation)
```

### 1.2 旋转对流感实现

| 关键机制 | 实现方式 |
|---------|---------|
| 持续旋转 | 每条线有独立 `rotSpeed`（rad/s），随时间累积 |
| 对流感 | 相邻线**反向旋转**：`rotDir = (index % 2 === 0) ? +1 : −1` |
| 层次差异 | 各线旋转速度略有差异（0.18–0.52 rad/s），线条缓慢漂移错开 |
| 有机变形 | 3 个径向谐波以不同速率独立漂移相位，曲线形状在旋转中持续变化 |
| 呼吸感 | 每条线的 alpha 以 0.8 Hz 微弱脉动（±0.2），相位按线条索引错开 |

### 1.3 参数设计

```
线条数量：5–9 条（随机初始化，LOW_END 设备固定 5 条）
基准半径：R_base ∈ [0.55, 0.83]（相对于 canvas 短边 × 0.44）
主谐波幅度：A1 ∈ [0.22, 0.43]
次谐波幅度：A2 ∈ [0.12, 0.24]
慢wobble幅度：A3 = 0.08（固定）
旋转速度：|rotSpeed| ∈ [0.18, 0.52] rad/s
相位漂移：drift1 ∈ [0.29, 0.69], drift2 ∈ [0.17, 0.89]
每条线采样点：200 pts（LOW_END 降至 120 pts）
```

### 1.4 颜色方案（保留现有 TikTok 双色调）

- **Dark mode：** cyan `#00f2fe` / red `#fe0979`，`globalCompositeOperation: 'screen'`
- **Light mode：** cyan `#00a8c8` / red `#c8005a`，`globalCompositeOperation: 'multiply'`
- 线条按索引交替取色，奇偶不同色，叠交处产生混色发光
- 每条线两遍绘制：宽 glow pass（`shadowBlur`）+ 细核心线，复现霓虹感

### 1.5 圆形裁切

`ctx.clip()` 裁切到半径 `clipR = canvas短边 × 0.46`，确保所有曲线严格锁定在圆内，不溢出。

---

## 2. 改动范围

### 改动：`MusicWaveCanvas.vue`

**替换内容（仅 drawFrame 逻辑）：**

| 当前 | 替换后 |
|------|--------|
| `Ripple` 接口 + 生命周期管理 | 删除（无波纹生命周期概念） |
| `WAVE_LIFETIME`, `spawnInterval`, 生成/清理逻辑 | 删除 |
| `fractalNoise`, `smoothNoise`, `hash` 工具函数 | 删除 |
| `drawCore`（中心光晕） | 删除 |
| Lissajous-style drawFrame | 替换为极坐标旋转 drawFrame |
| `state.ripples`, `state.lastSpawn`, `state.nextRippleId` | 替换为 `state.lines`（静态参数数组，初始化一次） |

**保留不动：**
- `isLowEnd()` 设备检测
- `DPR`, `TARGET_FPS`, `FRAME_INTERVAL` 帧率控制
- 主题响应（`isDark`, `themeObserver`, `PALETTE`）
- `prefersReduced` 减弱动效支持
- `resize()` + `ResizeObserver`
- RAF 管理（`rafBox`, `loop`）
- `dismissing` prop + dismiss 状态机（缩放 + 淡出）
- `onMounted` / `onUnmounted` 生命周期

**新增：**
- `makeLineParams(index, total)` — 初始化每条线的极坐标参数
- `drawPolarCurve(ctx, cx, cy, R, params, t, alpha, lineWidth, palette)` — 单条曲线绘制

### 不改动的组件

| 组件 | 原因 |
|------|------|
| `LoadingOverlay.vue` | 仅组合 `GlassMask` + `MusicWaveCanvas`，无绘制逻辑 |
| `GlassMask.vue` | 毛玻璃背景层，与动画无关 |
| `useLoadingOverlay.ts` / `loading.ts` | 状态管理，无变化 |
| `router/guards/loading.ts` | 路由触发，无变化 |

---

## 3. 性能考量

### 3.1 每帧重绘开销对比

| 指标 | 当前波纹方案 | 新极坐标方案 |
|------|------------|------------|
| 活跃对象数 | 4–6 个 Ripple，动态生成/销毁 | 5–9 条线，静态参数，无 GC 压力 |
| 每帧计算点数 | 6 × 90 = 540 pts | 9 × 200 = 1800 pts（HIGH）/ 5 × 120 = 600 pts（LOW） |
| `fractalNoise` 调用 | 每点 2–3 次多层噪声 | 0（纯三角函数） |
| `shadowBlur` passes | 每 Ripple 1 次 | 每线 1 次 glow pass（相同） |
| 状态机复杂度 | 高（spawn/cleanup/lifetime） | 低（仅 dismiss 进度） |

新方案在高端设备上点数略多，但消除了 fractalNoise 的浮点运算和 Ripple 生命周期管理，综合 CPU 开销持平或更低。

### 3.2 低端设备降级

```
LOW_END 判断（复用现有逻辑）：
  cores ≤ 2 || deviceMemory ≤ 2

LOW_END 时：
  LINE_COUNT = 5（固定，不随机）
  STEPS per curve = 120（非 200）
  shadowBlur glow pass = 跳过（仅绘核心线）
  TARGET_FPS = 30（现有逻辑，不变）
```

### 3.3 减弱动效（prefers-reduced-motion）

复用现有逻辑：`prefersReduced.value === true` 时：
- 停止 alpha 脉动，固定 alpha = 0.6
- 旋转速度乘以 0.15（几乎静止，仅微弱漂移）
- `shadowBlur` 设为 0

### 3.4 DPR 与 canvas 尺寸

不变：`DPR = Math.min(devicePixelRatio, 2)`，`lineWidth = canvas短边 × 0.007 × DPR`。

---

## 4. 落地步骤

### Step 1：重写 `MusicWaveCanvas.vue` 绘制核心

- 删除 `Ripple` 接口、`fractalNoise`/`smoothNoise`/`hash`、`drawCore`、spawn 逻辑
- 新增 `makeLineParams`、`drawPolarCurve`
- 在 `state` 中将 `ripples[]` 替换为 `lines[]`（`onMounted` 时一次性初始化）
- `drawFrame` 改为：遍历 `lines`，计算 dismiss/breath alpha，调用 `drawPolarCurve`
- 保留所有非绘制逻辑（设备检测、主题、resize、dismiss 状态机）

### Step 2：验证

```bash
cd frontend/apps/main
npm run typecheck   # 无类型错误
npm run test:run    # 现有测试通过（loading composable 测试）
```

手工验证：
- [ ] Dark mode 旋转流动效果正常
- [ ] Light mode 颜色切换正常
- [ ] 路由切换触发/结束 loading 正常
- [ ] Dismiss 动画（缩放淡出）正常
- [ ] prefers-reduced-motion 下几乎静止
- [ ] 小尺寸（< 100px）不溢出圆形

### Step 3：提交

```
feat(auth): replace ripple waves with polar rotation loading animation
```

---

## 参考文件

- **Demo：** `loading-demo.html`（项目根目录，仅用于预览，不进入生产）
- **当前实现：** `frontend/packages/auth/src/components/MusicWaveCanvas.vue`
- **设计系统：** `frontend/apps/main/DESIGN.md`
