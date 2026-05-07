# 设备识别问题：同一设备每次登录被识别为新设备

## 问题现象

用户选择"记录当前设备"后，下次登录仍然提示记录设备。在"已登录设备"列表中，同一台 Chrome 浏览器显示为多个不同设备。

## 根因分析

### 数据流追踪

```
LoginPage.vue (onMounted)
  → getDeviceFingerprint()  // 生成指纹
  → checkDevice(fingerprint)  // 查询是否信任设备

AuthStore.trustDevice()
  → getDeviceFingerprint()  // 生成指纹
  → POST /auth/device/trust { fingerprint }  // 保存信任设备

Backend DeviceSession
  → browser_fingerprint 字段存储指纹
  → 查询时匹配 browser_fingerprint
```

### 根本原因

原始指纹生成逻辑使用了 `navigator.userAgent` 作为指纹组件：

```typescript
// 原始实现 (fingerprint.ts)
function collectComponents(): string {
  const components = [
    navigator.userAgent,  // ❌ 问题源头
    navigator.language,
    screen.width/height/colorDepth,
    // ...
  ]
  return components.join('|')
}
```

**问题**：Chrome 浏览器的 `userAgent` 包含版本号：

- 第一次登录：`Mozilla/5.0 ... Chrome/120.0.0.0 ...`
- 自动更新后：`Mozilla/5.0 ... Chrome/121.0.0.0 ...`

版本号变化导致 SHA-256 指纹完全不同，系统识别为新设备。

### 稳定性分析

| 组件 | 稳定性 | 说明 |
|------|--------|------|
| `navigator.userAgent` | ❌ 低 | 包含浏览器版本，自动更新后变化 |
| `navigator.language` | ⚠️ 中 | 用户可能手动切换语言 |
| `screen.*` | ✅ 高 | 硬件属性，稳定 |
| `Intl.DateTimeFormat().timeZone` | ✅ 高 | 时区设置，稳定 |
| `navigator.hardwareConcurrency` | ✅ 高 | CPU 核心数，稳定 |
| `navigator.maxTouchPoints` | ✅ 高 | 触摸点数，稳定 |
| `navigator.platform` | ✅ 高 | 操作系统平台，稳定 |

## 解决方案

采用方案 3：集成成熟的 FingerprintJS 开源库。

### 实施步骤

1. **安装依赖**
   ```bash
   pnpm add @fingerprintjs/fingerprintjs --filter @numina/auth
   ```

2. **重构指纹生成逻辑**
   - 使用 FingerprintJS 替换自定义实现
   - 保留 localStorage 持久化（向后兼容）
   - FingerprintJS 生成更稳定的 visitorId（60-80% 准确率）

3. **修改后的实现**
   ```typescript
   // frontend/packages/auth/src/utils/fingerprint.ts
   import FingerprintJS from '@fingerprintjs/fingerprintjs'

   export async function getDeviceFingerprint(): Promise<string> {
     try {
       // 检查 localStorage fallback（向后兼容）
       const storedFallback = localStorage.getItem('_numina_fp_fallback')
       if (storedFallback) return storedFallback

       // 使用 FingerprintJS
       const fp = await FingerprintJS.load()
       const result = await fp.get()

       // 持久化存储
       localStorage.setItem('_numina_fp_fallback', result.visitorId)

       return result.visitorId
     } catch {
       // Fallback: UUID
       const fallback = crypto.randomUUID().replace(/-/g, '')
       localStorage.setItem('_numina_fp_fallback', fallback)
       return fallback
     }
   }
   ```

### 为什么选择 FingerprintJS？

1. **稳定性**：组合多个浏览器特征（canvas, WebGL, fonts 等），浏览器版本更新不影响指纹
2. **隐私合规**：客户端计算，不上传数据到第三方服务器（开源版本）
3. **准确率**：60-80%，足够用于设备信任场景
4. **成熟度**：GitHub 27K stars，业界验证

## 验证测试

1. **类型检查通过**
   ```bash
   cd frontend/apps/main && npm run typecheck
   # ✅ 通过
   ```

2. **功能验证**
   - 同一设备多次登录应生成相同指纹
   - Chrome 更新后指纹应保持稳定
   - localStorage 清除后重新生成（符合预期）

## 隐私合规说明

FingerprintJS 开源版本：
- 客户端计算，不存储数据到服务器
- GDPR 合规（但需用户同意存储 visitorId）
- 无侵入性技术（canvas/audio 指纹可选）

## 相关文件

- `frontend/packages/auth/src/utils/fingerprint.ts` - 指纹生成逻辑
- `frontend/packages/auth/src/stores/auth.ts` - 信任设备调用
- `backend/app/routers/device.py` - 设备检查/信任 API
- `backend/app/models/device_session.py` - 设备会话模型

## 参考资源

- [FingerprintJS GitHub](https://github.com/fingerprintjs/fingerprintjs)
- [FingerprintJS npm](https://www.npmjs.com/package/@fingerprintjs/fingerprintjs)
- [Browser Fingerprinting Best Practices](https://blog.openreplay.com/browser-fingerprinting/)