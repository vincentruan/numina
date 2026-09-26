"""
安全监控服务 - 使用统一 Cache 层替代进程内存存储
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)


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


class SecurityMonitor:
    """
    安全监控器 — 使用统一 Cache 层

    功能:
    - 实时事件收集
    - 威胁检测规则引擎
    - 自动告警触发
    - 统计数据生成

    Redis 模式下，可疑 IP、安全计数器等跨 worker 共享。
    """

    # 威胁检测阈值配置
    THRESHOLDS = {
        "rate_limit_violations": {
            "count": 10,
            "window": 300,  # 5分钟
            "level": ThreatLevel.MEDIUM,
        },
        "suspicious_requests": {"count": 50, "window": 300, "level": ThreatLevel.HIGH},
        "unique_ips": {
            "count": 100,
            "window": 60,  # 1分钟
            "level": ThreatLevel.CRITICAL,
        },
        "data_volume": {
            "bytes": 100_000_000,  # 100MB
            "window": 300,
            "level": ThreatLevel.HIGH,
        },
    }

    def __init__(self):
        self.event_buffer: list[SecurityEvent] = []
        self.alert_handlers: list[Callable[[dict], Any]] = []

    def register_alert_handler(self, handler: Callable[[dict], Any]):
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

        # 存储到 Cache
        await self._store_event(event)

        # 实时威胁检测
        await self._check_threat(event)

    async def _store_event(self, event: SecurityEvent):
        """存储事件到 Cache"""
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_EVENT

        cache = get_cache()
        event_data = {
            "timestamp": event.timestamp.isoformat(),
            "level": event.threat_level.value,
            "ip": event.client_ip,
            "path": event.path,
            "details": event.details,
        }

        key = f"{SEC_EVENT}:{event.threat_type.value}"
        await cache.lpush(key, event_data, ttl=86400)  # 24h TTL

    async def _check_threat(self, event: SecurityEvent):
        """检查并触发威胁告警"""
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_SUSPECT

        cache = get_cache()

        # 检查IP是否已被标记
        if await cache.sismember(f"{SEC_SUSPECT}:global", event.client_ip):
            if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._trigger_alert(event)
            return

        # 分析事件模式
        threat_detected = await self._analyze_pattern(event)

        if threat_detected:
            await cache.sadd(f"{SEC_SUSPECT}:global", event.client_ip)
            await self._trigger_alert(event)

    async def _analyze_pattern(self, event: SecurityEvent) -> bool:
        """分析事件模式，检测威胁"""
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_COUNTER

        cache = get_cache()

        # 检查速率限制违规次数
        if event.threat_type == ThreatType.RATE_LIMIT_EXCEEDED:
            key = f"{SEC_COUNTER}:rate_violations:{event.client_ip}"
            count = await cache.increment(key, ttl=300)

            threshold = self.THRESHOLDS["rate_limit_violations"]
            if count >= threshold["count"]:
                return True

        # 检查可疑请求频率
        key = f"{SEC_COUNTER}:suspicious_count:{event.client_ip}"
        count = await cache.increment(key, ttl=300)

        return bool(count >= self.THRESHOLDS["suspicious_requests"]["count"])

    async def _trigger_alert(self, event: SecurityEvent):
        """触发告警"""
        alert_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": asdict(event),
            "recommendation": self._get_recommendation(event),
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
            ThreatType.INVALID_SIGNATURE: "Review client integrity",
        }
        return recommendations.get(event.threat_type, "Monitor and investigate")

    async def get_security_stats(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> dict:
        """获取安全统计信息"""
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_COUNTER, SEC_EVENT, SEC_SUSPECT

        cache = get_cache()
        start_time = start_time or datetime.now(UTC) - timedelta(hours=24)
        end_time = end_time or datetime.now(UTC)

        # Aggregate event counts by threat type
        events_by_type: dict[str, int] = {}
        for threat in ThreatType:
            key = f"{SEC_EVENT}:{threat.value}"
            items = await cache.lrange(key, 0, -1)
            if items:
                events_by_type[threat.value] = len(items)

        # Suspicious IP count
        suspect_ips = await cache.smembers(f"{SEC_SUSPECT}:global")
        suspicious_ip_count = len(suspect_ips)

        # Active counter keys (scan for counter prefix)
        # Rate violation counters are per-IP, we report aggregate
        counter_summary: dict[str, int] = {}
        # Scan recent events for IPs with violations
        rate_key = f"{SEC_EVENT}:{ThreatType.RATE_LIMIT_EXCEEDED.value}"
        rate_events = await cache.lrange(rate_key, 0, 99)
        unique_violation_ips = {e.get("ip", "") for e in rate_events if isinstance(e, dict)}
        for ip in unique_violation_ips:
            cnt_key = f"{SEC_COUNTER}:rate_violations:{ip}"
            val = await cache.get(cnt_key)
            if val is not None:
                counter_summary[f"rate_violations:{ip}"] = int(val)

        return {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "events_by_type": events_by_type,
            "suspicious_ip_count": suspicious_ip_count,
            "active_counters": counter_summary,
        }


# 全局监控器实例
_security_monitor: SecurityMonitor | None = None


def get_security_monitor() -> SecurityMonitor:
    """获取全局安全监控器实例"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor
