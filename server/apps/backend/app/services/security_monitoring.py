"""
安全监控服务 - 实时检测和告警异常行为
使用进程内存存储，无需Redis依赖（单机部署优化）
"""
import logging
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum

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
    details: dict
    user_id: str | None = None


class InMemorySecurityStore:
    """
    进程内存安全存储
    替代Redis的轻量级单机实现
    """
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
        """初始化存储结构"""
        # 事件存储: {event_type: [(timestamp, event_data), ...]}
        self._events: dict[str, list[tuple]] = defaultdict(list)
        # IP计数器: {counter_key: (count, expiry_timestamp)}
        self._counters: dict[str, tuple] = {}
        # 可疑IP集合
        self._suspicious_ips: set[str] = set()
        # 锁保护
        self._store_lock = threading.RLock()
        # 最后清理时间
        self._last_cleanup = time.time()

    def _cleanup_expired(self):
        """清理过期数据"""
        now = time.time()
        # 每5分钟清理一次
        if now - self._last_cleanup < 300:
            return

        with self._store_lock:
            # 清理过期计数器
            expired_keys = [
                k for k, (_, expiry) in self._counters.items()
                if expiry < now
            ]
            for k in expired_keys:
                del self._counters[k]

            # 清理过期事件（24小时前）
            cutoff = now - 86400
            for event_type in list(self._events.keys()):
                self._events[event_type] = [
                    (ts, data) for ts, data in self._events[event_type]
                    if ts > cutoff
                ]
                if not self._events[event_type]:
                    del self._events[event_type]

            self._last_cleanup = now

    def add_event(self, event_type: str, event_data: dict, timestamp: float):
        """添加事件"""
        self._cleanup_expired()
        with self._store_lock:
            self._events[event_type].append((timestamp, event_data))

    def get_event_count(self, event_type: str, start_time: float, end_time: float) -> int:
        """获取事件数量"""
        with self._store_lock:
            events = self._events.get(event_type, [])
            return sum(1 for ts, _ in events if start_time <= ts <= end_time)

    def increment_counter(self, key: str, expiry: int) -> int:
        """增加计数器并返回新值"""
        now = time.time()
        with self._store_lock:
            if key in self._counters:
                count, _ = self._counters[key]
                count += 1
            else:
                count = 1
            self._counters[key] = (count, now + expiry)
            return count

    def add_suspicious_ip(self, ip: str):
        """添加可疑IP"""
        with self._store_lock:
            self._suspicious_ips.add(ip)

    def is_suspicious_ip(self, ip: str) -> bool:
        """检查IP是否可疑"""
        with self._store_lock:
            return ip in self._suspicious_ips

    def get_stats(self, start_time: float, end_time: float) -> dict:
        """获取统计信息"""
        with self._store_lock:
            stats = {
                "events_by_type": {},
                "suspicious_ip_count": len(self._suspicious_ips),
                "active_counters": len(self._counters),
            }
            for event_type, events in self._events.items():
                count = sum(1 for ts, _ in events if start_time <= ts <= end_time)
                if count > 0:
                    stats["events_by_type"][event_type] = count
            return stats


class SecurityMonitor:
    """
    安全监控器 - 纯内存版（无需Redis）

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

    def __init__(self):
        self._store = InMemorySecurityStore()
        self.event_buffer: list[SecurityEvent] = []
        self.alert_handlers: list[callable] = []

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

        # 存储到内存
        await self._store_event(event)

        # 实时威胁检测
        await self._check_threat(event)

    async def _store_event(self, event: SecurityEvent):
        """存储事件到内存"""
        event_data = {
            "timestamp": event.timestamp.isoformat(),
            "level": event.threat_level.value,
            "ip": event.client_ip,
            "path": event.path,
            "details": event.details
        }

        self._store.add_event(
            event.threat_type.value,
            event_data,
            event.timestamp.timestamp()
        )

    async def _check_threat(self, event: SecurityEvent):
        """检查并触发威胁告警"""
        # 检查IP是否已被标记
        if self._store.is_suspicious_ip(event.client_ip):
            if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._trigger_alert(event)
            return

        # 分析事件模式
        threat_detected = await self._analyze_pattern(event)

        if threat_detected:
            self._store.add_suspicious_ip(event.client_ip)
            await self._trigger_alert(event)

    async def _analyze_pattern(self, event: SecurityEvent) -> bool:
        """分析事件模式，检测威胁"""
        # 检查速率限制违规次数
        if event.threat_type == ThreatType.RATE_LIMIT_EXCEEDED:
            key = f"rate_violations:{event.client_ip}"
            count = self._store.increment_counter(key, 300)

            threshold = self.THRESHOLDS["rate_limit_violations"]
            if count >= threshold["count"]:
                return True

        # 检查可疑请求频率
        key = f"suspicious_count:{event.client_ip}"
        count = self._store.increment_counter(key, 300)

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
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> dict:
        """获取安全统计信息"""
        start_time = start_time or datetime.utcnow() - timedelta(hours=24)
        end_time = end_time or datetime.utcnow()

        stats = self._store.get_stats(
            start_time.timestamp(),
            end_time.timestamp()
        )

        return {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            **stats
        }


# 全局监控器实例
_security_monitor: SecurityMonitor | None = None


def get_security_monitor() -> SecurityMonitor:
    """获取全局安全监控器实例"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor
