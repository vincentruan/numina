"""Backend 内部 HTTP 客户端。

所有对 backend 的调用都通过此客户端，自动附加：
- Authorization: Bearer {AGENT_INTERNAL_TOKEN}
- X-Family-Id: {family_id}

backend 端点验证这两个 header，强制以 family_id 为边界过滤数据。
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 超时配置
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


class BackendClient:
    """面向对象封装，绑定 family_id，供各 service 使用。"""

    def __init__(self, family_id: str):
        self.family_id = family_id

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

    async def get_family_ai_config(self) -> dict:
        return await get_family_ai_config(self.family_id)


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
    """获取家庭 Dashboard overview 数据。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/overview",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_dashboard_allocation(family_id: str) -> dict:
    """获取资产配置分布数据。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/allocation",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_dashboard_trend(family_id: str, period: str = "year") -> dict:
    """获取净资产趋势数据。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/trend",
            params={"period": period},
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_dashboard_low_usage(family_id: str) -> list:
    """获取低使用率资产列表。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/low-usage",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_dashboard_daily_cost(family_id: str) -> list:
    """获取日均成本排行数据。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/daily-cost-ranking",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_liabilities(family_id: str) -> list:
    """获取家庭活跃负债列表。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/liabilities",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_assets_expiring_soon(family_id: str, days_threshold: int = 180) -> list:
    """获取即将到期的资产列表。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/dashboard/expiring-soon",
            params={"days_threshold": days_threshold},
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_family_ai_config(family_id: str) -> dict:
    """获取家庭 AI 配置（provider + 解密后的 api_key）。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/ai/config",
            headers=_make_headers(family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)


async def get_ai_enabled_families(any_family_id: str) -> list[str]:
    """获取所有已开启 AI 功能的家庭 ID 列表（定时任务使用）。

    backend 的 verify_agent_token 要求 X-Family-Id header，
    定时任务调用时传入任意一个有效 family_id 即可（结果不受其过滤）。
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.BACKEND_BASE_URL}/api/v1/internal/ai/enabled-families",
            headers=_make_headers(any_family_id),
        )
        resp.raise_for_status()
        return _unwrap(resp)
