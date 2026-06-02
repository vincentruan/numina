"""Backend 内部 HTTP 客户端。

所有对 backend 的调用都通过此客户端，自动附加：
- Authorization: Bearer {AGENT_INTERNAL_TOKEN}
- X-Family-Id: {family_id}

backend 端点验证这两个 header，强制以 family_id 为边界过滤数据。

⚠️ 租户隔离原则：所有操作必须绑定 family_id，禁止跨家庭数据访问。
"""

import logging
import re

import httpx

from apps.agent.app.config import settings

logger = logging.getLogger(__name__)

# Backend uses numeric Snowflake family IDs. Older agent tests and golden fixtures
# still use fam-* IDs, so accept both formats while rejecting path/control input.
_FAMILY_ID_PATTERN = re.compile(r"^(?:\d{8,20}|fam-[a-z0-9-]{8,36})$")


def _validate_family_id(family_id: str) -> str:
    """验证 family_id 格式，防止注入攻击。

    Args:
        family_id: 家庭 ID

    Returns:
        验证后的 family_id

    Raises:
        ValueError: family_id 格式无效
    """
    if not _FAMILY_ID_PATTERN.match(family_id):
        raise ValueError(
            f"Invalid family_id format: '{family_id}'. "
            "Expected numeric Snowflake ID or fam-{8-36 alphanumeric chars}"
        )
    return family_id


# 超时配置
# 数据密集型操作（dashboard、资产列表）使用标准超时
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
# 配置查询类操作使用快速超时（AI config、enabled families）
_CONFIG_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0)

# Connection pool 配置
# 优化：复用连接，减少 TCP handshake 开销（预计 30-50% latency 降低）
_POOL_LIMITS = httpx.Limits(
    max_connections=20,  # 最大并发连接数
    max_keepalive_connections=10,  # keep-alive 连接池大小
    keepalive_expiry=30.0,  # keep-alive 30秒过期
)

# 共享连接池客户端（延迟初始化）
_shared_client: httpx.AsyncClient | None = None


async def get_shared_client() -> httpx.AsyncClient:
    """获取共享连接池客户端。

    Connection pooling benefits:
    - Reuses TCP connections, reduces handshake overhead
    - Estimated 30-50% latency reduction for repeated calls
    - Automatic connection lifecycle management

    Returns:
        共享的 AsyncClient 实例
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=_POOL_LIMITS,
            base_url=settings.BACKEND_BASE_URL,
        )
        logger.debug(
            "Created shared backend client with pool: max_conn=%d, keepalive=%d",
            _POOL_LIMITS.max_connections,
            _POOL_LIMITS.max_keepalive_connections,
        )
    return _shared_client


async def close_shared_client() -> None:
    """关闭共享连接池（应用 shutdown 时调用）。"""
    global _shared_client
    if _shared_client and not _shared_client.is_closed:
        await _shared_client.aclose()
        logger.debug("Closed shared backend client pool")


class BackendClient:
    """面向对象封装，绑定 family_id，供各 service 使用。

    所有方法自动验证 family_id 格式，防止注入攻击。
    """

    def __init__(self, family_id: str):
        self.family_id = _validate_family_id(family_id)

    def _headers(self) -> dict[str, str]:
        return _make_headers(self.family_id)

    async def get_dashboard_overview(self) -> dict:
        return await get_dashboard_overview(self.family_id)

    async def get_dashboard_allocation(self) -> dict:
        return await get_dashboard_allocation(self.family_id)

    async def get_dashboard_trend(self, period: str = "year") -> dict:
        return await get_dashboard_trend(self.family_id, period)

    async def get_dashboard_low_usage(self) -> list:
        return await get_dashboard_low_usage(self.family_id)

    async def get_dashboard_daily_cost(self) -> list:
        return await get_dashboard_daily_cost(self.family_id)

    async def get_liabilities(self) -> list:
        return await get_liabilities(self.family_id)

    async def get_assets_expiring_soon(self, days_threshold: int = 365) -> list:
        return await get_assets_expiring_soon(self.family_id, days_threshold)

    async def get_agent_config(self, agent_id: int) -> dict:
        """Fetch agent configuration from backend internal API."""
        validated_id = _validate_family_id(self.family_id)
        client = await get_shared_client()
        resp = await client.get(
            f"/api/v1/internal/ai/agents/{agent_id}",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)

    async def get_enabled_skills(self) -> list[dict]:
        """Fetch enabled skill registry records for the family."""
        validated_id = _validate_family_id(self.family_id)
        client = await get_shared_client()
        resp = await client.get(
            f"/api/v1/internal/skill-registry/{validated_id}",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        data = _unwrap(resp)
        if isinstance(data, list):
            return [s for s in data if s.get("is_enabled", True)]
        return []

    async def get_enabled_mcp_servers(self) -> list[dict]:
        """Fetch enabled MCP servers for the family."""
        validated_id = _validate_family_id(self.family_id)
        client = await get_shared_client()
        resp = await client.get(
            "/api/v1/internal/ai/mcp-servers",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        data = _unwrap(resp)
        return data if isinstance(data, list) else []

    async def get_family_ai_config(self) -> dict:
        return await get_family_ai_config(self.family_id)

    async def get_family_ai_configs(self) -> dict:
        return await get_family_ai_config(self.family_id)

    async def upsert_session(
        self,
        *,
        session_id: str,
        user_id: str | None,
        capability: str,
        agent_id: str | None = None,
        jsonl_path: str,
        last_model: str | None = None,
    ) -> None:
        await upsert_session(
            self.family_id,
            session_id=session_id,
            user_id=user_id,
            capability=capability,
            agent_id=agent_id,
            jsonl_path=jsonl_path,
            last_model=last_model,
        )

    async def update_session_summary(
        self,
        *,
        session_id: str,
        summary: str | None,
        model: str | None = None,
        status: str = "completed",
        title: str | None = None,
    ) -> None:
        await update_session_summary(
            self.family_id,
            session_id=session_id,
            summary=summary,
            model=model,
            status=status,
            title=title,
        )

    async def list_sessions(self, *, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        return await list_sessions(self.family_id, limit=limit, offset=offset)

    async def get_session(self, session_id: str) -> dict | None:
        return await get_session(self.family_id, session_id)

    async def report_circuit_event(
        self,
        config_id: str,
        error_code: int,
        error_type: str,
        error_message: str | None = None,
    ) -> dict:
        return await report_circuit_event(
            self.family_id, config_id, error_code, error_type, error_message
        )

    async def report_half_open_result(self, config_id: str, success: bool) -> dict:
        """报告 half-open 状态下的调用结果。"""
        return await report_half_open_result(self.family_id, config_id, success)

    async def reset_circuit_success(self, config_id: str) -> dict:
        return await reset_circuit_success(self.family_id, config_id)

    async def get_user(self, user_id: str) -> dict | None:
        """Get user info by user_id for title generation."""
        return await get_user(self.family_id, user_id)


def classify_error_type(error_code: int, error_message: str | None = None) -> str:
    """根据 HTTP 错误码和错误消息分类错误类型。

    Args:
        error_code: HTTP 状态码或异常标识
        error_message: 错误消息（可选，用于检测账号删除等特殊错误）

    Returns:
        错误类型字符串：
        - permanent_auth: 401, 403 (认证错误，需手动恢复)
        - permanent_account: 410 或账号删除相关消息
        - transient_rate_limit: 429 (速率限制)
        - transient_server: 500, 502, 503, 504 (服务器错误)
        - transient_timeout: timeout 异常 (error_code = 0 或特殊标识)
        - transient_network: 其他网络错误
    """
    if error_code in (401, 403):
        return "permanent_auth"
    if error_code == 410:
        return "permanent_account"
    if error_message and any(
        keyword in error_message.lower()
        for keyword in ["invalid key", "invalid api key", "api key expired"]
    ):
        return "permanent_auth"
    if error_message and any(
        keyword in error_message.lower()
        for keyword in ["deleted", "suspended", "account"]
    ):
        return "permanent_account"
    if error_code == 429:
        return "transient_rate_limit"
    if error_code in (500, 502, 503, 504):
        return "transient_server"
    if error_code == 0 or error_code == -1:  # Timeout or connection error
        return "transient_timeout"
    # Default to transient for unknown codes
    return "transient_network"


def _make_headers(family_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.AGENT_INTERNAL_TOKEN}",
        "X-Family-Id": family_id,
        "Content-Type": "application/json",
    }


def _unwrap(resp: httpx.Response) -> dict | list:
    """Unwrap the standard backend envelope {"code": "OK", "data": ...}."""
    body = resp.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


async def get_dashboard_overview(family_id: str) -> dict:
    """获取家庭 Dashboard overview 数据。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        Dashboard overview 数据

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/overview",
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_dashboard_allocation(family_id: str) -> dict:
    """获取资产配置分布数据。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        资产配置分布数据

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/allocation",
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_dashboard_trend(family_id: str, period: str = "year") -> dict:
    """获取净资产趋势数据。

    Args:
        family_id: 家庭 ID（自动验证格式）
        period: 时间周期（year/month）

    Returns:
        净资产趋势数据

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/trend",
        params={"period": period},
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_dashboard_low_usage(family_id: str) -> list:
    """获取低使用率资产列表。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        低使用率资产列表

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/low-usage",
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_dashboard_daily_cost(family_id: str) -> list:
    """获取日均成本排行数据。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        日均成本排行数据

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/daily-cost-ranking",
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_liabilities(family_id: str) -> list:
    """获取家庭活跃负债列表。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        家庭活跃负债列表

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/liabilities",
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_assets_expiring_soon(family_id: str, days_threshold: int = 180) -> list:
    """获取即将到期的资产列表。

    Args:
        family_id: 家庭 ID（自动验证格式）
        days_threshold: 天数阈值（默认180天）

    Returns:
        即将到期的资产列表

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/dashboard/expiring-soon",
        params={"days_threshold": days_threshold},
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    return _unwrap(resp)


async def get_family_ai_config(family_id: str) -> dict:
    """获取家庭 AI 配置（provider + 解密后的 api_key）。

    注意：此函数使用快速超时（_CONFIG_TIMEOUT），不共享连接池。

    Args:
        family_id: 家庭 ID（自动验证格式）

    Returns:
        家庭 AI 配置数据

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    # 使用独立 client 以应用快速超时
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.get(
            "/api/v1/internal/ai/config",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_ai_enabled_families() -> list[str]:
    """获取所有已开启 AI 功能的家庭 ID 列表（定时任务使用）。

    注意：此函数目前存在设计缺陷，需要重构。
    正确做法：定时任务应按家庭维度分别启动，每个家庭使用自己的 AI 配置。
    当前实现：使用 backend 的 admin endpoint 获取列表（无需 X-Family-Id）。

    TODO: 重构为按家庭维度调度，避免租户隔离违反。
    """
    # 使用独立 client 以应用快速超时（admin endpoint 无需共享池）
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.get(
            "/api/v1/admin/ai/enabled-families",
            headers={
                "Authorization": f"Bearer {settings.AGENT_INTERNAL_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def upsert_session(
    family_id: str,
    *,
    session_id: str,
    user_id: str | None,
    capability: str,
    agent_id: str | None = None,
    jsonl_path: str,
    last_model: str | None = None,
) -> None:
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    payload: dict = {
        "session_id": session_id,
        "user_id": user_id,
        "capability": capability,
        "agent_id": agent_id,
        "jsonl_path": jsonl_path,
        "last_model": last_model,
    }
    resp = await client.post(
        "/api/v1/internal/ai/sessions/upsert",
        json=payload,
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()


async def update_session_summary(
    family_id: str,
    *,
    session_id: str,
    summary: str | None,
    model: str | None = None,
    status: str = "completed",
    title: str | None = None,
) -> None:
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    payload: dict = {"summary": summary, "model": model, "status": status}
    if title is not None:
        payload["title"] = title
    resp = await client.post(
        f"/api/v1/internal/ai/sessions/{session_id}/summary",
        json=payload,
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()


async def list_sessions(
    family_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        "/api/v1/internal/ai/sessions",
        params={"limit": limit, "offset": offset},
        headers=_make_headers(validated_id),
    )
    resp.raise_for_status()
    body = _unwrap(resp)
    if isinstance(body, dict):
        return body.get("sessions", []), body.get("total", 0)
    return [], 0


async def get_session(family_id: str, session_id: str) -> dict | None:
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    resp = await client.get(
        f"/api/v1/internal/ai/sessions/{session_id}",
        headers=_make_headers(validated_id),
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _unwrap(resp)


async def report_circuit_event(
    family_id: str,
    config_id: str,
    error_code: int,
    error_type: str,
    error_message: str | None = None,
) -> dict:
    """报告供应商调用失败，触发熔断计数。

    Args:
        family_id: 家庭 ID（自动验证格式）
        config_id: AI 配置 ID
        error_code: HTTP 错误码或异常类型
        error_type: 错误类型分类（permanent_auth, transient_rate_limit 等），必填
        error_message: 错误消息（可选）

    Returns:
        熔断状态响应
    """
    validated_id = _validate_family_id(family_id)
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        payload: dict = {"error_code": error_code, "error_type": error_type}
        if error_message:
            payload["error_message"] = error_message
        resp = await client.post(
            f"/api/v1/internal/ai/config/{config_id}/circuit-event",
            json=payload,
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def reset_circuit_success(family_id: str, config_id: str) -> dict:
    """成功调用后重置熔断计数。"""
    validated_id = _validate_family_id(family_id)
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.post(
            f"/api/v1/internal/ai/config/{config_id}/circuit-reset",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_user(family_id: str, user_id: str) -> dict | None:
    """Get user info by user_id for title generation."""
    validated_id = _validate_family_id(family_id)
    client = await get_shared_client()
    try:
        resp = await client.get(
            f"/api/v1/internal/users/{user_id}",
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)
    except httpx.HTTPStatusError:
        return None


async def report_half_open_result(
    family_id: str,
    config_id: str,
    success: bool,
) -> dict:
    """报告 half-open 状态下的调用结果（成功或失败）。

    Args:
        family_id: 家庭 ID（自动验证格式）
        config_id: AI 配置 ID
        success: 调用是否成功

    Returns:
        熔断状态响应，包含累计计数
    """
    validated_id = _validate_family_id(family_id)
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.post(
            f"/api/v1/internal/ai/config/{config_id}/half-open-result",
            json={"success": success},
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def report_web_search_circuit(family_id: str, provider_id: int, failure_type: str) -> None:
    """Report web search tool failure to trigger circuit breaker.

    Args:
        family_id: 家庭 ID（自动验证格式）
        provider_id: Web search provider ID
        failure_type: Failure type classification

    Raises:
        ValueError: family_id 格式无效
        httpx.HTTPStatusError: Backend API 错误
    """
    validated_id = _validate_family_id(family_id)
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.post(
            f"/api/v1/internal/ai/web-search/{provider_id}/circuit",
            json={"failure_type": failure_type},
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
