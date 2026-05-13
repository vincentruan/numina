"""WebDAV storage backend."""
import ipaddress
import mimetypes
from urllib.parse import urlparse

import httpx

from packages.storage.base import (
    StorageAuthError,
    StorageBackend,
    StorageConnectionError,
)

# Private/reserved IPv4 ranges that must not be reachable via user-supplied URLs
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def _validate_webdav_url(url: str) -> None:
    """Raise ValueError if url is not a safe http/https URL for WebDAV use."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"WebDAV URL 必须使用 http 或 https 协议，当前: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("WebDAV URL 缺少主机名")
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ValueError(f"WebDAV URL 指向受限主机名，拒绝: {hostname}")
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                raise ValueError(f"WebDAV URL 指向受限地址范围，拒绝: {hostname}")
    except ValueError as exc:
        if "WebDAV" in str(exc) or "受限" in str(exc):
            raise
        # hostname is a domain name — allow it


class WebDAVStorageBackend(StorageBackend):
    """Stores files on a WebDAV server."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
    ) -> None:
        _validate_webdav_url(base_url)
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            auth=httpx.BasicAuth(username, password),
            verify=verify_ssl,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=120.0, pool=5.0),
        )

    async def _ensure_path(self, date_dir: str) -> None:
        """MKCOL each cumulative path segment of date_dir."""
        segments = [s for s in date_dir.split("/") if s]
        cumulative = ""
        for segment in segments:
            cumulative = f"{cumulative}/{segment}" if cumulative else segment
            url = f"{self._base_url}/{cumulative}"
            try:
                response = await self._client.request("MKCOL", url)
            except httpx.TransportError as exc:
                raise StorageConnectionError(str(exc)) from exc
            if response.status_code not in (201, 405):
                raise StorageConnectionError(
                    f"MKCOL {url} 返回 {response.status_code}"
                )

    async def save(self, content: bytes, filename: str, date_dir: str) -> str:
        """Upload content via PUT and return the remote_path."""
        remote_path = f"{date_dir}/{filename}"
        await self._ensure_path(date_dir)
        url = f"{self._base_url}/{remote_path}"
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = "application/octet-stream"
        try:
            response = await self._client.put(
                url,
                content=content,
                headers={"Content-Type": content_type},
            )
        except httpx.TransportError as exc:
            raise StorageConnectionError(str(exc)) from exc
        if response.status_code in (201, 204):
            return remote_path
        if response.status_code in (401, 403):
            raise StorageAuthError(f"WebDAV 认证失败: {response.status_code}")
        raise StorageConnectionError(f"PUT {url} 返回 {response.status_code}")

    async def delete(self, remote_path: str) -> None:
        """DELETE a file or collection at remote_path."""
        url = f"{self._base_url}/{remote_path}"
        try:
            response = await self._client.delete(url, headers={"Depth": "infinity"})
        except httpx.TransportError as exc:
            raise StorageConnectionError(str(exc)) from exc
        if response.status_code in (204, 404):
            return
        if response.status_code in (401, 403):
            raise StorageAuthError(f"WebDAV 认证失败: {response.status_code}")
        raise StorageConnectionError(f"DELETE {url} 返回 {response.status_code}")

    def get_url(self, remote_path: str) -> str:
        """Return the full URL for the given remote_path."""
        return f"{self._base_url}/{remote_path}"

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
