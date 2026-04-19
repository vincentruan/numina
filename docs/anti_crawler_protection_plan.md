# Numina 反爬虫防护方案

> **Document Type**: ce:refactor
> **Target**: 为Numina家庭资产可视化SaaS平台设计完整的多层反爬虫体系
> **Tech Stack**: FastAPI + Vue3 + Nginx + Docker
> **Deployment**: 单机部署，进程内存存储（无Redis依赖）

---

## 📋 需求分析

### 项目背景
- **平台**: Numina - 家庭资产可视化SaaS平台
- **敏感数据**: 家庭资产数据、财务信息、个人敏感信息
- **架构**: FastAPI后端 + Vue3前端 + Nginx反向代理
    - **部署**: Docker Compose容器化部署，单机架构
    - **存储**: 进程内存存储（替代Redis，简化部署）

### 主要威胁
1. **数据爬取**: API接口被恶意批量调用获取资产数据
2. **账户攻击**: 登录接口暴力破解、凭证填充
3. **API滥用**: AI报告生成等高计算资源接口被滥用
4. **自动化工具**: Selenium、Playwright、Puppeteer等自动化浏览器
5. **绕过手段**: 代理IP轮换、User-Agent伪造、请求频率控制

---

## 🎯 架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         反爬虫防护四层架构                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 4 │  🛡️ 边缘防护层 (Edge Protection)                            │
│          │  CDN / WAF / DDoS防护 / IP信誉库                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 3 │  🌐 网关防护层 (Gateway Protection)                          │
│          │  Nginx限流 / IP黑名单 / Bot检测 / TLS指纹校验                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 2 │  ⚡ 应用防护层 (Application Protection)                       │
│          │  FastAPI中间件 / 速率限制 / JWT验证 / API行为分析              │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 1 │  💻 前端防护层 (Client Protection)                            │
│          │  Vue3反调试 / 请求签名 / 动态Token / 行为验证                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Layer 1: 前端防护层 (Vue3)

### 1.1 动态请求签名机制

**文件位置**: `frontend/src/utils/request-signer.ts`

```typescript
/**
 * 请求签名工具 - 防止API被直接调用
 * 基于时间窗口 + 随机数 + 用户会话的签名机制
 */
export class RequestSigner {
  private static readonly SECRET_ROTATION_INTERVAL = 300000; // 5分钟
  private static readonly TOKEN_KEY = 'numina_sig_token';
  
  /**
   * 生成请求签名
   * 算法: HMAC-SHA256(timestamp + nonce + path, session_secret)
   */
  static generateSignature(path: string, payload?: object): SignatureData {
    const timestamp = Date.now();
    const nonce = this.generateNonce();
    const token = this.getOrCreateToken();
    
    const signature = this.computeHMAC(
      `${timestamp}:${nonce}:${path}:${JSON.stringify(payload || {})}`,
      token
    );
    
    return {
      'X-Sig-Timestamp': timestamp.toString(),
      'X-Sig-Nonce': nonce,
      'X-Sig-Hash': signature,
      'X-Sig-Version': 'v1'
    };
  }
  
  private static generateNonce(): string {
    // 使用Crypto API生成加密安全的随机数
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    return Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
  }
  
  private static computeHMAC(data: string, key: string): string {
    // 使用Web Crypto API计算HMAC
    const encoder = new TextEncoder();
    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      encoder.encode(key),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const signature = await crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(data));
    return Array.from(new Uint8Array(signature), b => b.toString(16).padStart(2, '0')).join('');
  }
}

interface SignatureData {
  'X-Sig-Timestamp': string;
  'X-Sig-Nonce': string;
  'X-Sig-Hash': string;
  'X-Sig-Version': string;
}
```

### 1.2 反调试与自动化检测

**文件位置**: `frontend/src/composables/use-anti-crawler.ts`

```typescript
import { onMounted, onUnmounted } from 'vue';

/**
 * 反爬虫检测组合式函数
 * 检测自动化浏览器、调试工具、异常行为
 */
export function useAntiCrawler() {
  let detectionInterval: number | null = null;
  
  const detectAutomation = (): boolean => {
    const indicators = [
      // 检测Chrome DevTools Protocol
      !!(window as any).__webdriver_script_fn,
      !!(window as any).cdc_adoQpoasnfa76pfcZLmcfl_Array,
      !!(window as any).cdc_adoQpoasnfa76pfcZLmcfl_Promise,
      !!(window as any).cdc_adoQpoasnfa76pfcZLmcfl_Symbol,
      // 检测Selenium
      !!(window as any).document.__selenium_evaluate,
      !!(window as any).document.__webdriver_evaluate,
      !!(window as any).navigator.webdriver === true,
      // 检测PhantomJS
      !!(window as any).callPhantom,
      !!(window as any)._phantom,
      // 检测Nightmare
      !!(window as any).__nightmare,
      // 检测自动化特征
      navigator.plugins.length === 0,
      navigator.languages.length === 0,
      screen.width === 0 && screen.height === 0,
    ];
    
    const automationScore = indicators.filter(Boolean).length;
    return automationScore >= 2; // 2个以上特征触发警告
  };
  
  const detectDevTools = (): boolean => {
    const threshold = 160;
    const widthThreshold = window.outerWidth - window.innerWidth > threshold;
    const heightThreshold = window.outerHeight - window.innerHeight > threshold;
    
    // 检测开发者工具打开
    if (widthThreshold || heightThreshold) {
      return true;
    }
    
    // 检测调试器
    const start = performance.now();
    debugger; // 如果DevTools打开，这会导致延迟
    const end = performance.now();
    
    return end - start > 100;
  };
  
  const detectHeadless = (): boolean => {
    // 检测无头浏览器特征
    const userAgent = navigator.userAgent.toLowerCase();
    const isHeadless = userAgent.includes('headless') || 
                       userAgent.includes('phantom') ||
                       userAgent.includes('selenium');
    
    // 检测WebGL
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    const debugInfo = gl?.getExtension('WEBGL_debug_renderer_info');
    const renderer = debugInfo ? gl?.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : '';
    
    return isHeadless || renderer?.includes('SwiftShader') || false;
  };
  
  const reportSuspicious = (type: string, details: object) => {
    // 发送可疑行为报告到后端
    fetch('/api/v1/security/suspicious-activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type,
        details,
        timestamp: Date.now(),
        url: window.location.href,
        userAgent: navigator.userAgent
      })
    }).catch(() => {}); // 静默失败
  };
  
  const checkAndReport = () => {
    const isAutomated = detectAutomation();
    const isHeadless = detectHeadless();
    
    if (isAutomated || isHeadless) {
      reportSuspicious('automation_detected', {
        isAutomated,
        isHeadless,
        userAgent: navigator.userAgent
      });
      
      // 可选: 重定向到验证码或封禁页面
      // window.location.href = '/blocked';
    }
  };
  
  onMounted(() => {
    // 初始检测
    checkAndReport();
    
    // 定期检查
    detectionInterval = window.setInterval(checkAndReport, 30000);
  });
  
  onUnmounted(() => {
    if (detectionInterval) {
      clearInterval(detectionInterval);
    }
  });
  
  return {
    detectAutomation,
    detectDevTools,
    detectHeadless
  };
}
```

### 1.3 API请求封装增强

**文件位置**: `frontend/src/api/client.ts`

```typescript
import axios from 'axios';
import { RequestSigner } from '@/utils/request-signer';
import { useAuthStore } from '@/stores/auth';

/**
 * 增强型API客户端 - 集成反爬虫机制
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  }
});

// 请求拦截器 - 添加签名
apiClient.interceptors.request.use(
  async (config) => {
    // 生成请求签名
    const signature = await RequestSigner.generateSignature(
      config.url || '',
      config.data
    );
    
    Object.entries(signature).forEach(([key, value]) => {
      config.headers[key] = value;
    });
    
    // 添加行为指纹
    config.headers['X-Behavior-Data'] = JSON.stringify({
      screenResolution: `${screen.width}x${screen.height}`,
      colorDepth: screen.colorDepth,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      language: navigator.language,
      platform: navigator.platform
    });
    
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 处理反爬虫响应
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 429) {
      // 触发速率限制，显示验证码
      const authStore = useAuthStore();
      await authStore.showCaptchaChallenge();
    }
    
    if (error.response?.status === 403 && 
        error.response?.data?.code === 'SUSPICIOUS_ACTIVITY') {
      // 可疑活动检测，记录并重定向
      console.warn('Suspicious activity detected');
      window.location.href = '/security-check';
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## ⚡ Layer 2: 应用防护层 (FastAPI)

### 2.1 速率限制中间件

**文件位置**: `backend/app/middleware/rate_limit.py`

当前项目已使用进程内存实现速率限制，无需Redis依赖：

```python
"""
智能速率限制中间件 - 单机内存版（无Redis依赖）

特点:
- 进程内存存储，无需额外服务
- 自动清理过期数据
- 适用于单机部署

注意: 多worker部署时，各worker独立计数，实际限流阈值 = worker数 × 配置阈值
"""
import time
import hashlib
from typing import Optional, Dict, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dataclasses import dataclass
from enum import Enum
import threading


class RateLimitTier(Enum):
    """速率限制等级"""
    STRICT = "strict"      # 严格限制 (登录、注册)
    STANDARD = "standard"  # 标准限制 (普通API)
    RELAXED = "relaxed"    # 宽松限制 (只读查询)
    AI_HEAVY = "ai_heavy"  # AI资源限制 (报告生成)


@dataclass
class RateLimitRule:
    """速率限制规则"""
    tier: RateLimitTier
    requests: int
    window: int  # 秒
    block_duration: int  # 秒


# 全局内存存储 - 替代Redis
class InMemoryRateStore:
    """进程内存速率限制存储"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_storage()
        return cls._instance

    def _init_storage(self):
        self._counters: Dict[str, tuple] = {}  # {key: (count, expiry_timestamp)}
        self._blocked: Dict[str, float] = {}   # {key: unblock_timestamp}
        self._store_lock = threading.RLock()
        self._last_cleanup = time.time()

    def _cleanup_expired(self):
        now = time.time()
        if now - self._last_cleanup < 60:  # 每分钟清理一次
            return
        with self._store_lock:
            expired_counters = [k for k, (_, expiry) in self._counters.items() if expiry < now]
            for k in expired_counters:
                del self._counters[k]
            expired_blocks = [k for k, unblock_time in self._blocked.items() if unblock_time < now]
            for k in expired_blocks:
                del self._blocked[k]
            self._last_cleanup = now

    def is_blocked(self, key: str) -> Optional[int]:
        """检查是否被封禁，返回剩余秒数"""
        self._cleanup_expired()
        with self._store_lock:
            if key in self._blocked:
                remaining = int(self._blocked[key] - time.time())
                if remaining > 0:
                    return remaining
                else:
                    del self._blocked[key]
            return None

    def increment_and_check(self, key: str, window: int, limit: int, block_duration: int) -> tuple[bool, int, int]:
        """增加计数并检查限制"""
        self._cleanup_expired()
        now = time.time()
        with self._store_lock:
            if key in self._counters:
                count, expiry = self._counters[key]
                if expiry < now:  # 窗口过期，重置
                    count = 0
            else:
                count = 0

            count += 1
            expiry = now + window
            self._counters[key] = (count, expiry)

            remaining = max(0, limit - count)
            reset_time = int(expiry)

            if count > limit:
                # 触发封禁
                self._blocked[key] = now + block_duration
                return False, 0, int(self._blocked[key])

            return True, remaining, reset_time


RATE_LIMIT_RULES: Dict[str, RateLimitRule] = {
    # 认证相关 - 严格限制
    "/api/v1/auth/login": RateLimitRule(
        tier=RateLimitTier.STRICT,
        requests=5,
        window=300,
        block_duration=1800
    ),
    "/api/v1/auth/register": RateLimitRule(
        tier=RateLimitTier.STRICT,
        requests=3,
        window=3600,
        block_duration=3600
    ),
    "/api/v1/auth/refresh": RateLimitRule(
        tier=RateLimitTier.STRICT,
        requests=10,
        window=300,
        block_duration=900
    ),

    # AI生成 - 资源限制
    "/api/v1/ai/report": RateLimitRule(
        tier=RateLimitTier.AI_HEAVY,
        requests=3,
        window=3600,
        block_duration=7200
    ),

    # 资产数据 - 标准限制
    "/api/v1/assets": RateLimitRule(
        tier=RateLimitTier.STANDARD,
        requests=100,
        window=60,
        block_duration=300
    ),

    # 导出功能 - 严格限制
    "/api/v1/export": RateLimitRule(
        tier=RateLimitTier.STRICT,
        requests=5,
        window=3600,
        block_duration=3600
    ),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    智能速率限制中间件 - 内存版

    功能:
    - 基于路径的精细化速率限制
    - 进程内存存储（无Redis依赖）
    - 渐进式惩罚机制
    - 客户端指纹识别
    """

    def __init__(
        self,
        app,
        rules: Optional[Dict[str, RateLimitRule]] = None
    ):
        super().__init__(app)
        self.store = InMemoryRateStore()
        self.rules = rules or RATE_LIMIT_RULES
        self._ip_reputation: Dict[str, float] = {}

    def _get_client_fingerprint(self, request: Request) -> str:
        """
        生成客户端指纹
        结合IP + User-Agent + 部分请求头
        """
        components = [
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("sec-ch-ua", ""),
        ]
        fingerprint = hashlib.sha256(
            "|".join(components).encode()
        ).hexdigest()[:16]
        return fingerprint
    
    def _get_rate_limit_key(self, request: Request, rule: RateLimitRule) -> str:
        """生成速率限制键（内存版）"""
        fingerprint = self._get_client_fingerprint(request)
        path_hash = hashlib.sha256(
            request.url.path.encode()
        ).hexdigest()[:8]
        return f"ratelimit:{rule.tier.value}:{fingerprint}:{path_hash}"

    async def _is_blocked(self, request: Request) -> Optional[int]:
        """检查是否被封禁"""
        block_key = self._get_block_key(request)
        return self.store.is_blocked(block_key)

    async def _check_rate_limit(
        self,
        request: Request,
        rule: RateLimitRule
    ) -> tuple[bool, int, int]:
        """
        检查速率限制

        Returns:
            (是否允许, 剩余次数, 重置时间)
        """
        key = self._get_rate_limit_key(request, rule)
        return self.store.increment_and_check(
            key, rule.window, rule.requests, rule.block_duration
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """中间件主逻辑"""
        # 匹配速率限制规则
        rule = self._match_rule(request.url.path)
        
        if rule:
            # 检查是否被封禁
            block_ttl = await self._is_blocked(request)
            if block_ttl:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "RATE_LIMIT_BLOCKED",
                        "message": f"Access blocked. Retry after {block_ttl} seconds",
                        "retry_after": block_ttl
                    },
                    headers={"Retry-After": str(block_ttl)}
                )
            
            # 检查速率限制
            allowed, remaining, reset_time = await self._check_rate_limit(
                request, rule
            )
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded",
                        "retry_after": rule.block_duration
                    },
                    headers={"Retry-After": str(rule.block_duration)}
                )
            
            # 添加速率限制头
            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            return response
        
        return await call_next(request)
    
    def _match_rule(self, path: str) -> Optional[RateLimitRule]:
        """匹配速率限制规则"""
        # 精确匹配
        if path in self.rules:
            return self.rules[path]
        
        # 前缀匹配
        for prefix, rule in self.rules.items():
            if path.startswith(prefix):
                return rule
        
        # 默认规则
        return RateLimitRule(
            tier=RateLimitTier.STANDARD,
            requests=60,
            window=60,
            block_duration=300
        )
```

### 2.2 请求签名验证中间件

**文件位置**: `backend/app/middleware/signature_verification.py`

```python
"""
请求签名验证中间件 - 验证前端生成的签名
防止直接API调用和重放攻击
"""
import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SignatureVerificationMiddleware(BaseHTTPMiddleware):
    """
    请求签名验证中间件
    
    验证:
    - 时间戳有效性 (5分钟窗口)
    - Nonce唯一性 (防重放)
    - 签名正确性
    - 行为数据一致性
    """
    
    def __init__(
        self,
        app,
        secret_key: str,
        timestamp_tolerance: int = 300,  # 5分钟容差
        skip_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.secret_key = secret_key.encode()
        self.timestamp_tolerance = timestamp_tolerance
        self.skip_paths = set(skip_paths or [
            "/api/v1/health",
            "/api/v1/docs",
            "/api/v1/openapi.json"
        ])
        self._seen_nonces: set = set()  # 生产环境应使用Redis
    
    async def dispatch(self, request: Request, call_next):
        # 跳过指定路径
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # GET请求可选验证
        if request.method == "GET" and not request.headers.get("X-Sig-Hash"):
            return await call_next(request)
        
        # 提取签名头
        timestamp_str = request.headers.get("X-Sig-Timestamp")
        nonce = request.headers.get("X-Sig-Nonce")
        signature = request.headers.get("X-Sig-Hash")
        version = request.headers.get("X-Sig-Version", "v1")
        
        # 检查必需头
        if not all([timestamp_str, nonce, signature]):
            return JSONResponse(
                status_code=403,
                content={
                    "code": "MISSING_SIGNATURE",
                    "message": "Request signature required"
                }
            )
        
        # 验证时间戳
        try:
            timestamp = int(timestamp_str)
            now = int(time.time() * 1000)
            
            if abs(now - timestamp) > self.timestamp_tolerance * 1000:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "INVALID_TIMESTAMP",
                        "message": "Request timestamp out of valid range"
                    }
                )
        except ValueError:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "INVALID_TIMESTAMP",
                    "message": "Invalid timestamp format"
                }
            )
        
        # 验证Nonce (防重放)
        if nonce in self._seen_nonces:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "REPLAY_DETECTED",
                    "message": "Request already processed"
                }
            )
        
        # 验证签名
        body = await request.body()
        expected_signature = self._compute_signature(
            timestamp_str, nonce, request.url.path, body, version
        )
        
        if not hmac.compare_digest(expected_signature, signature):
            return JSONResponse(
                status_code=403,
                content={
                    "code": "INVALID_SIGNATURE",
                    "message": "Request signature verification failed"
                }
            )
        
        # 记录Nonce (生产环境应使用Redis并设置TTL)
        self._seen_nonces.add(nonce)
        
        # 验证行为数据 (可选)
        behavior_data = request.headers.get("X-Behavior-Data")
        if behavior_data:
            is_suspicious = self._analyze_behavior(behavior_data)
            if is_suspicious:
                # 记录可疑但不阻断，用于分析
                request.state.suspicious_behavior = True
        
        return await call_next(request)
    
    def _compute_signature(
        self,
        timestamp: str,
        nonce: str,
        path: str,
        body: bytes,
        version: str
    ) -> str:
        """计算期望的签名"""
        data = f"{timestamp}:{nonce}:{path}:{body.decode()}"
        
        signature = hmac.new(
            self.secret_key,
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _analyze_behavior(self, behavior_data: str) -> bool:
        """
        分析行为数据，检测异常
        
        例如:
        - 屏幕分辨率异常 (如0x0)
        - 缺少浏览器特征
        - 时区与用户IP不匹配
        """
        try:
            import json
            data = json.loads(behavior_data)
            
            # 检查异常指标
            red_flags = 0
            
            # 分辨率检查
            resolution = data.get("screenResolution", "")
            if resolution in ["0x0", "1x1", ""]:
                red_flags += 1
            
            # 语言检查
            if not data.get("language"):
                red_flags += 1
            
            # 平台检查
            if not data.get("platform"):
                red_flags += 1
            
            return red_flags >= 2
            
        except Exception:
            return True  # 解析失败视为可疑
```

### 2.3 Bot检测中间件

**文件位置**: `backend/app/middleware/bot_detection.py`

```python
"""
Bot检测中间件 - 识别自动化爬虫和工具
"""
import re
from typing import Optional, List, Set
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class BotDetectionMiddleware(BaseHTTPMiddleware):
    """
    Bot检测中间件
    
    检测:
    - 已知爬虫User-Agent
    - 缺少浏览器特征
    - 异常请求模式
    """
    
    # 已知爬虫User-Agent模式
    CRAWLER_PATTERNS: List[str] = [
        # 搜索引擎爬虫 (根据需要可放行)
        r"googlebot",
        r"bingbot",
        r"slurp",  # Yahoo
        r"duckduckbot",
        
        # 爬虫框架
        r"scrapy",
        r"curl",
        r"wget",
        r"python-requests",
        r"aiohttp",
        r"httpx",
        r"axios",
        r"okhttp",
        r"httpclient",
        
        # 自动化工具
        r"selenium",
        r"headlesschrome",
        r"phantomjs",
        r"puppeteer",
        r"playwright",
        r"cypress",
        
        # 数据抓取服务
        r"scrapinghub",
        r"screaming\s*frog",
        r"ahrefsbot",
        r"mj12bot",
        r"semrush",
    ]
    
    # 浏览器必需特征
    REQUIRED_BROWSER_HEADERS: List[str] = [
        "accept",
        "accept-language",
        "accept-encoding",
    ]
    
    def __init__(
        self,
        app,
        block_crawlers: bool = True,
        allow_search_engines: bool = False,
        custom_patterns: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.block_crawlers = block_crawlers
        self.allow_search_engines = allow_search_engines
        
        # 编译正则
        patterns = custom_patterns or self.CRAWLER_PATTERNS
        if allow_search_engines:
            # 移除搜索引擎模式
            patterns = [p for p in patterns if not any(
                se in p.lower() 
                for se in ["googlebot", "bingbot", "duckduckbot"]
            )]
        
        self.crawler_regex = re.compile(
            "|".join(patterns),
            re.IGNORECASE
        )
    
    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("user-agent", "").lower()
        
        # 检测爬虫User-Agent
        if self.crawler_regex.search(user_agent):
            if self.block_crawlers:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "CRAWLER_DETECTED",
                        "message": "Automated access not permitted"
                    }
                )
            else:
                # 记录但不阻断
                request.state.is_crawler = True
        
        # 检测缺少浏览器特征
        if self._is_missing_browser_features(request):
            request.state.suspicious_client = True
        
        # 检测异常请求模式
        if self._has_anomalous_patterns(request):
            request.state.anomalous_behavior = True
        
        return await call_next(request)
    
    def _is_missing_browser_features(self, request: Request) -> bool:
        """检查是否缺少浏览器必需特征"""
        headers = request.headers
        
        missing = sum(
            1 for header in self.REQUIRED_BROWSER_HEADERS
            if not headers.get(header)
        )
        
        # 缺少2个以上视为可疑
        return missing >= 2
    
    def _has_anomalous_patterns(self, request: Request) -> bool:
        """检测异常请求模式"""
        headers = request.headers
        
        # 检查是否同时缺少referer和origin
        if not headers.get("referer") and not headers.get("origin"):
            return True
        
        # 检查Accept头
        accept = headers.get("accept", "")
        if "*/*" == accept and request.method in ["POST", "PUT", "DELETE"]:
            return True
        
        return False
```

### 2.4 集成到FastAPI应用

**文件位置**: `backend/app/main.py` (关键修改)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.signature_verification import SignatureVerificationMiddleware
from app.middleware.bot_detection import BotDetectionMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动: 初始化中间件
    for middleware in app.user_middleware:
        if hasattr(middleware, "startup"):
            await middleware.startup()
    
    yield
    
    # 关闭: 清理资源
    pass


app = FastAPI(
    title="Numina API",
    lifespan=lifespan
)

# 添加中间件 (顺序很重要，从外到内)

# 1. Bot检测 (最外层)
app.add_middleware(
    BotDetectionMiddleware,
    block_crawlers=True,
    allow_search_engines=False
)

# 2. 速率限制 - 无需Redis，使用内存存储
app.add_middleware(RateLimitMiddleware)

# 3. 签名验证
app.add_middleware(
    SignatureVerificationMiddleware,
    secret_key=os.getenv("SIG_SECRET_KEY", "your-secret-key"),
    timestamp_tolerance=300
)

# 4. CORS (签名验证之后)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[
        "*",
        "X-Sig-Timestamp",
        "X-Sig-Nonce",
        "X-Sig-Hash",
        "X-Sig-Version",
        "X-Behavior-Data"
    ]
)
```

---

## 🌐 Layer 3: 网关防护层 (Nginx)

### 3.1 增强版Nginx配置

**文件位置**: `nginx.production.conf`

```nginx
# Numina Production Nginx Configuration with Anti-Crawler Protection

# 上游服务定义
upstream backend {
    server backend:8000;
    keepalive 32;
}

upstream frontend {
    server frontend:80;
    keepalive 32;
}

# 限速区域定义
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=1r/s;
limit_req_zone $binary_remote_addr zone=ai_limit:10m rate=0.1r/s;

# 连接限制
limit_conn_zone $binary_remote_addr zone=addr:10m;

# 爬虫User-Agent映射
map $http_user_agent $is_crawler {
    default 0;
    ~*(scrapy|curl|wget|python-requests|aiohttp|httpx|axios|okhttp) 1;
    ~*(selenium|headlesschrome|phantomjs|puppeteer|playwright) 1;
    ~*(scrapinghub|screaming\sfrog|ahrefsbot|mj12bot|semrush) 1;
}

# 可疑IP映射
map $remote_addr $is_blocked_ip {
    default 0;
    # 在这里添加已知恶意IP
    # include /etc/nginx/conf.d/blocked_ips.conf;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 10M;
    client_body_timeout 30s;
    client_header_timeout 30s;
    
    # 日志格式 (包含更多安全信息)
    log_format security '$remote_addr - $remote_user [$time_local] '
                       '"$request" $status $body_bytes_sent '
                       '"$http_referer" "$http_user_agent" '
                       '$request_time $upstream_response_time '
                       '$http_x_sig_hash $http_x_sig_version';
    
    access_log /var/log/nginx/access.log security;
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.1: 基础安全防护
    # ═══════════════════════════════════════════════════════════════
    
    # 阻止已知的恶意IP
    if ($is_blocked_ip) {
        return 444;
    }
    
    # 阻止无User-Agent的请求
    if ($http_user_agent = "") {
        return 444;
    }
    
    # 阻止常见爬虫
    if ($is_crawler) {
        return 444;
    }
    
    # 阻止非标准HTTP方法
    if ($request_method !~ ^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$) {
        return 444;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.2: 内部API保护
    # ═══════════════════════════════════════════════════════════════
    
    location ^~ /api/v1/internal {
        return 403;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.3: WebSocket特殊配置
    # ═══════════════════════════════════════════════════════════════
    
    location /api/v1/ai/report/ws {
        # WebSocket限速
        limit_req zone=ai_limit burst=5 nodelay;
        
        proxy_pass http://backend/api/v1/ai/report/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket特定超时
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
        
        # 连接限制
        limit_conn addr 1;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.4: 登录/认证API严格限速
    # ═══════════════════════════════════════════════════════════════
    
    location ~ ^/api/v1/auth/(login|register|refresh)$ {
        # 严格限速: 每秒1个请求
        limit_req zone=login_limit burst=3 nodelay;
        limit_req_status 429;
        
        # 连接限制
        limit_conn addr 5;
        limit_conn_status 429;
        
        # 添加安全头
        add_header X-RateLimit-Zone "login" always;
        
        proxy_pass http://backend/api/v1/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.5: AI资源API严格限速
    # ═══════════════════════════════════════════════════════════════
    
    location ~ ^/api/v1/ai/ {
        # AI资源限速: 每10秒1个请求
        limit_req zone=ai_limit burst=2 nodelay;
        limit_req_status 429;
        
        # 连接限制
        limit_conn addr 2;
        
        proxy_pass http://backend/api/v1/ai/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.6: 通用API标准限速
    # ═══════════════════════════════════════════════════════════════
    
    location /api/ {
        # 标准限速: 每秒10个请求
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;
        
        # 连接限制
        limit_conn addr 10;
        
        proxy_pass http://backend/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        
        # 错误处理
        proxy_intercept_errors on;
        error_page 429 /429.html;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.7: OpenAPI文档保护
    # ═══════════════════════════════════════════════════════════════
    
    location = /openapi.json {
        # 限制对API文档的访问
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;
        
        proxy_pass http://backend/openapi.json;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.8: 静态站点配置 (保持不变)
    # ═══════════════════════════════════════════════════════════════
    
    location /overview/ {
        alias /usr/share/nginx/site/overview/;
        try_files $uri $uri/ /overview/index.html;
        expires 7d;
        add_header Cache-Control "public, immutable";
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
    
    location /project/ {
        alias /usr/share/nginx/site/project/;
        try_files $uri $uri/ /project/index.html;
        expires 7d;
        add_header Cache-Control "public, immutable";
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
    
    location /site/assets/ {
        alias /usr/share/nginx/site/assets/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location = /site/style.css {
        alias /usr/share/nginx/site/style.css;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.9: 前端SPA配置
    # ═══════════════════════════════════════════════════════════════
    
    location / {
        # 安全头
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
        
        # CSP (根据实际资源调整)
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' /api/" always;
        
        proxy_pass http://frontend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.10: 错误页面
    # ═══════════════════════════════════════════════════════════════
    
    location = /429.html {
        internal;
        return 429 '{"code":"RATE_LIMIT","message":"Too many requests"}';
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Layer 3.11: Gzip压缩
    # ═══════════════════════════════════════════════════════════════
    
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
    gzip_min_length 1000;
}
```

### 3.2 IP黑名单管理脚本

**文件位置**: `scripts/manage-blocked-ips.sh`

```bash
#!/bin/bash
# Numina IP黑名单管理脚本
# 用于添加/删除/查看被封禁的IP

BLOCKED_IPS_FILE="/etc/nginx/conf.d/blocked_ips.conf"
NGINX_CONTAINER="numina-nginx"

# 创建黑名单文件(如果不存在)
init_blocklist() {
    if [ ! -f "$BLOCKED_IPS_FILE" ]; then
        sudo mkdir -p "$(dirname $BLOCKED_IPS_FILE)"
        echo "# Numina Blocked IPs" | sudo tee "$BLOCKED_IPS_FILE"
        echo "# Format: deny IP; # Reason" | sudo tee -a "$BLOCKED_IPS_FILE"
    fi
}

# 添加IP到黑名单
block_ip() {
    local ip=$1
    local reason=${2:-"Manual block"}
    local duration=${3:-"permanent"}
    
    if ! grep -q "deny $ip;" "$BLOCKED_IPS_FILE"; then
        echo "deny $ip; # $reason ($duration)" | sudo tee -a "$BLOCKED_IPS_FILE"
        reload_nginx
        echo "IP $ip blocked successfully"
    else
        echo "IP $ip already blocked"
    fi
}

# 从黑名单移除IP
unblock_ip() {
    local ip=$1
    
    if grep -q "deny $ip;" "$BLOCKED_IPS_FILE"; then
        sudo sed -i "/deny $ip;/d" "$BLOCKED_IPS_FILE"
        reload_nginx
        echo "IP $ip unblocked successfully"
    else
        echo "IP $ip not found in blocklist"
    fi
}

# 查看黑名单
list_blocked() {
    if [ -f "$BLOCKED_IPS_FILE" ]; then
        echo "=== Blocked IPs ==="
        grep "^deny" "$BLOCKED_IPS_FILE" || echo "No IPs blocked"
    else
        echo "Blocklist not initialized"
    fi
}

# 重载Nginx
reload_nginx() {
    if docker ps | grep -q "$NGINX_CONTAINER"; then
        docker exec "$NGINX_CONTAINER" nginx -s reload
    else
        echo "Warning: Nginx container not running"
    fi
}

# 主命令处理
case "$1" in
    init)
        init_blocklist
        ;;
    block)
        block_ip "$2" "$3" "$4"
        ;;
    unblock)
        unblock_ip "$2"
        ;;
    list)
        list_blocked
        ;;
    *)
        echo "Usage: $0 {init|block <ip> [reason] [duration]|unblock <ip>|list}"
        exit 1
        ;;
esac
```

---

## 🔍 Layer 4: 监控告警层

### 4.1 安全监控日志配置

**文件位置**: `backend/app/services/security_monitoring.py`

```python
"""
安全监控服务 - 实时检测和告警异常行为
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger("security")


class ThreatLevel(Enum):
    """威胁等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """威胁类型"""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_LOGIN = "suspicious_login"
    BOT_DETECTED = "bot_detected"
    DATA_SCRAPING = "data_scraping"
    API_ABUSE = "api_abuse"
    REPLAY_ATTACK = "replay_attack"
    INVALID_SIGNATURE = "invalid_signature"


@dataclass
class SecurityEvent:
    """安全事件"""
    timestamp: datetime
    threat_type: ThreatType
    threat_level: ThreatLevel
    client_ip: str
    user_agent: str
    path: str
    details: Dict
    user_id: Optional[str] = None


class SecurityMonitor:
    """
    安全监控器
    
    功能:
    - 实时事件收集
    - 威胁检测规则引擎
    - 自动告警触发
    - 统计数据生成
    """
    
    # 威胁检测阈值配置
    THRESHOLDS = {
        "rate_limit_violations": {
            "count": 10,
            "window": 300,  # 5分钟
            "level": ThreatLevel.MEDIUM
        },
        "suspicious_requests": {
            "count": 50,
            "window": 300,
            "level": ThreatLevel.HIGH
        },
        "unique_ips": {
            "count": 100,
            "window": 60,   # 1分钟
            "level": ThreatLevel.CRITICAL
        },
        "data_volume": {
            "bytes": 100_000_000,  # 100MB
            "window": 300,
            "level": ThreatLevel.HIGH
        }
    }
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.event_buffer: List[SecurityEvent] = []
        self.alert_handlers: List[callable] = []
        self.suspicious_ips: Set[str] = set()
    
    def register_alert_handler(self, handler: callable):
        """注册告警处理器"""
        self.alert_handlers.append(handler)
    
    async def log_event(self, event: SecurityEvent):
        """记录安全事件"""
        # 添加到缓冲
        self.event_buffer.append(event)
        
        # 持久化到日志
        logger.warning(
            f"Security Event: {event.threat_type.value} "
            f"[{event.threat_level.value}] from {event.client_ip}"
        )
        
        # 存储到Redis用于分析
        if self.redis:
            await self._store_event(event)
        
        # 实时威胁检测
        await self._check_threat(event)
    
    async def _store_event(self, event: SecurityEvent):
        """存储事件到Redis"""
        event_key = f"security:events:{event.threat_type.value}"
        event_data = json.dumps({
            "timestamp": event.timestamp.isoformat(),
            "level": event.threat_level.value,
            "ip": event.client_ip,
            "path": event.path,
            "details": event.details
        })
        
        # 使用Redis Stream或Sorted Set
        await self.redis.zadd(
            event_key,
            {event_data: event.timestamp.timestamp()}
        )
        
        # 设置过期
        await self.redis.expire(event_key, 86400)  # 24小时
    
    async def _check_threat(self, event: SecurityEvent):
        """检查并触发威胁告警"""
        # 检查IP是否已被标记
        if event.client_ip in self.suspicious_ips:
            if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._trigger_alert(event)
            return
        
        # 分析事件模式
        threat_detected = await self._analyze_pattern(event)
        
        if threat_detected:
            self.suspicious_ips.add(event.client_ip)
            await self._trigger_alert(event)
    
    async def _analyze_pattern(self, event: SecurityEvent) -> bool:
        """分析事件模式，检测威胁"""
        if not self.redis:
            return False
        
        # 检查速率限制违规次数
        if event.threat_type == ThreatType.RATE_LIMIT_EXCEEDED:
            key = f"security:ip:{event.client_ip}:rate_violations"
            count = await self.redis.incr(key)
            await self.redis.expire(key, 300)
            
            threshold = self.THRESHOLDS["rate_limit_violations"]
            if count >= threshold["count"]:
                return True
        
        # 检查可疑请求频率
        key = f"security:ip:{event.client_ip}:suspicious_count"
        count = await self.redis.incr(key)
        await self.redis.expire(key, 300)
        
        threshold = self.THRESHOLDS["suspicious_requests"]
        if count >= threshold["count"]:
            return True
        
        return False
    
    async def _trigger_alert(self, event: SecurityEvent):
        """触发告警"""
        alert_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": asdict(event),
            "recommendation": self._get_recommendation(event)
        }
        
        # 调用所有告警处理器
        for handler in self.alert_handlers:
            try:
                await handler(alert_data)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def _get_recommendation(self, event: SecurityEvent) -> str:
        """根据事件类型生成处置建议"""
        recommendations = {
            ThreatType.RATE_LIMIT_EXCEEDED: "Consider blocking IP temporarily",
            ThreatType.BOT_DETECTED: "Implement CAPTCHA challenge",
            ThreatType.DATA_SCRAPING: "Enable request signature verification",
            ThreatType.API_ABUSE: "Review and tighten rate limits",
            ThreatType.SUSPICIOUS_LOGIN: "Require MFA verification",
            ThreatType.REPLAY_ATTACK: "Check nonce validation",
            ThreatType.INVALID_SIGNATURE: "Review client integrity"
        }
        return recommendations.get(
            event.threat_type, 
            "Monitor and investigate"
        )
    
    async def get_security_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """获取安全统计信息"""
        if not self.redis:
            return {}
        
        start_time = start_time or datetime.utcnow() - timedelta(hours=24)
        end_time = end_time or datetime.utcnow()
        
        stats = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "events_by_type": {},
            "top_threat_ips": [],
            "threat_level_distribution": {}
        }
        
        # 统计各类型事件数量
        for threat_type in ThreatType:
            key = f"security:events:{threat_type.value}"
            count = await self.redis.zcount(
                key,
                start_time.timestamp(),
                end_time.timestamp()
            )
            stats["events_by_type"][threat_type.value] = count
        
        return stats


# 告警处理器示例
async def slack_alert_handler(alert_data: Dict):
    """Slack告警处理器"""
    import aiohttp
    
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    message = {
        "text": f"🚨 Security Alert",
        "attachments": [{
            "color": "danger",
            "fields": [
                {
                    "title": "Threat Type",
                    "value": alert_data["event"]["threat_type"],
                    "short": True
                },
                {
                    "title": "IP Address",
                    "value": alert_data["event"]["client_ip"],
                    "short": True
                },
                {
                    "title": "Recommendation",
                    "value": alert_data["recommendation"],
                    "short": False
                }
            ]
        }]
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json=message)


async def email_alert_handler(alert_data: Dict):
    """邮件告警处理器"""
    # 实现邮件发送逻辑
    pass


# 全局监控器实例
security_monitor = SecurityMonitor()
security_monitor.register_alert_handler(slack_alert_handler)
```

### 4.2 Docker Compose集成Redis

**文件位置**: `docker-compose.production.yml` (扩展)

```yaml
services:
  # 现有服务...
  
  # 新增: Redis用于速率限制和监控
  redis:
    image: redis:7-alpine
    container_name: numina-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    expose:
      - "6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  redis_data:
```

---

## 📊 部署清单

### 环境变量配置

**文件位置**: `.env.production.example` (新增)

```bash
# ═══════════════════════════════════════════════════════════════
# 反爬虫安全配置
# ═══════════════════════════════════════════════════════════════

# Redis配置 (用于分布式速率限制)
REDIS_URL=redis://numina-redis:6379/0

# 请求签名密钥 (前端和后端必须一致)
SIG_SECRET_KEY=your-secure-random-key-at-least-32-chars

# 速率限制配置
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_TIER=standard

# 告警配置
SECURITY_ALERT_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK
SECURITY_ALERT_EMAIL=security@your-domain.com

# Bot检测
BLOCK_CRAWLERS=true
ALLOW_SEARCH_ENGINES=false

# 注意: Redis依赖已移除，速率限制和安全监控使用进程内存存储
```

### 部署步骤

```bash
# 1. 克隆代码并进入目录
cd ~/data/numina

# 2. 配置环境变量
cp .env.production.example .env.production
# 编辑 .env.production 设置密钥和其他配置

# 3. 创建所需目录
mkdir -p data logs

# 4. 部署服务（无需Redis）
docker compose -f docker-compose.production.yml up -d --build

# 5. 验证部署
curl -I http://localhost/api/v1/health
curl -I http://localhost/api/v1/assets \
  -H "X-Sig-Timestamp: $(date +%s)000" \
  -H "X-Sig-Nonce: test" \
  -H "X-Sig-Hash: test"
```

---

## 🎯 效果评估

### 防护效果指标

| 指标 | 目标值 | 检测方法 |
|------|--------|----------|
| API未授权访问率 | < 0.1% | 安全日志分析 |
| 爬虫拦截率 | > 95% | Bot检测统计 |
| 误拦截率 | < 1% | 用户反馈+日志 |
| 平均响应延迟增加 | < 10ms | 性能测试 |
| 告警响应时间 | < 5分钟 | 告警日志 |

### 持续优化

1. **定期分析**: 每周审查安全日志，调整阈值
2. **规则更新**: 每月更新爬虫User-Agent黑名单
3. **渗透测试**: 每季度进行红队演练
4. **用户反馈**: 建立误拦截申诉渠道

---

## 📚 参考资源

- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Rate_Limiting_Cheat_Sheet.html)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Nginx Rate Limiting](https://www.nginx.com/blog/rate-limiting-nginx/)
- [Cloudflare Bot Management](https://developers.cloudflare.com/bots/)
