"""GitHub Contents API storage backend."""
import base64

import httpx

from packages.storage.base import (
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageFileSizeError,
    StorageRateLimitError,
)

# GitHub Contents API hard limit is 1MB for the base64-encoded payload.
# Base64 expands size by ~33%, so raw content must stay under 750KB to be safe.
_MAX_CONTENT_BYTES = 750 * 1024


class GitHubStorageBackend(StorageBackend):
    """Stores files in a GitHub repository via the Contents API."""

    def __init__(self, token: str, repo: str, branch: str = "main") -> None:
        self._token = token
        self._repo = repo
        self._branch = branch
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            base_url="https://api.github.com",
        )
        self._sha_cache: dict[str, str] = {}

    @property
    def write_delay_range(self) -> tuple[float, float]:
        """GitHub Contents API has stricter secondary rate limits — use longer jitter."""
        return (1.0, 3.0)

    def _check_rate_limit(self, response: httpx.Response) -> None:
        if response.headers.get("x-ratelimit-remaining") == "0":
            reset_at = int(response.headers.get("x-ratelimit-reset", 0))
            raise StorageRateLimitError(reset_at=reset_at)

    async def save(self, content: bytes, filename: str, date_dir: str, family_id: str = "", user_id: str = "") -> str:
        if len(content) > _MAX_CONTENT_BYTES:
            raise StorageFileSizeError(
                f"文件 {filename} 过大 ({len(content)} bytes)，"
                f"GitHub Contents API 限制 {_MAX_CONTENT_BYTES} bytes (base64 后 ~1MB)",
                file_size=len(content),
                max_size=_MAX_CONTENT_BYTES,
            )

        remote_path = f"{date_dir}/{filename}"
        b64 = base64.b64encode(content).decode()

        for _ in range(3):
            body: dict = {
                "message": f"upload {filename}",
                "content": b64,
                "branch": self._branch,
            }
            if remote_path in self._sha_cache:
                body["sha"] = self._sha_cache[remote_path]

            try:
                response = await self._client.put(
                    f"/repos/{self._repo}/contents/{remote_path}",
                    json=body,
                )
            except httpx.TransportError as exc:
                raise StorageConnectionError(str(exc)) from exc

            self._check_rate_limit(response)

            if response.status_code in (200, 201):
                self._sha_cache[remote_path] = response.json()["content"]["sha"]
                return remote_path

            if response.status_code == 409:
                self._sha_cache.pop(remote_path, None)
                try:
                    get_resp = await self._client.get(
                        f"/repos/{self._repo}/contents/{remote_path}",
                        params={"ref": self._branch},
                    )
                except httpx.TransportError as exc:
                    raise StorageConnectionError(str(exc)) from exc

                self._check_rate_limit(get_resp)

                if get_resp.status_code == 200:
                    self._sha_cache[remote_path] = get_resp.json()["sha"]
                continue

            if response.status_code in (401, 403):
                raise StorageAuthError(f"GitHub 认证失败: {response.status_code}")

            if response.status_code in (413, 422):
                # 413 = Payload Too Large, 422 = Unprocessable Entity (also used for size violations)
                raise StorageFileSizeError(
                    f"GitHub 拒绝上传 {filename}: HTTP {response.status_code} (文件可能过大)",
                    file_size=len(content),
                    max_size=_MAX_CONTENT_BYTES,
                )

        raise StorageConflictError(f"GitHub 冲突无法解决，已重试 3 次: {remote_path}")

    async def delete(self, remote_path: str) -> None:
        sha = self._sha_cache.get(remote_path)

        if sha is None:
            try:
                get_resp = await self._client.get(
                    f"/repos/{self._repo}/contents/{remote_path}",
                    params={"ref": self._branch},
                )
            except httpx.TransportError as exc:
                raise StorageConnectionError(str(exc)) from exc

            self._check_rate_limit(get_resp)

            if get_resp.status_code == 404:
                return
            sha = get_resp.json()["sha"]

        for attempt in range(2):
            try:
                response = await self._client.request(
                    "DELETE",
                    f"/repos/{self._repo}/contents/{remote_path}",
                    json={
                        "message": f"delete {remote_path}",
                        "sha": sha,
                        "branch": self._branch,
                    },
                )
            except httpx.TransportError as exc:
                raise StorageConnectionError(str(exc)) from exc

            self._check_rate_limit(response)

            if response.status_code == 404:
                self._sha_cache.pop(remote_path, None)
                return

            if response.status_code == 200:
                self._sha_cache.pop(remote_path, None)
                return

            if response.status_code == 409 and attempt == 0:
                try:
                    get_resp = await self._client.get(
                        f"/repos/{self._repo}/contents/{remote_path}",
                        params={"ref": self._branch},
                    )
                except httpx.TransportError as exc:
                    raise StorageConnectionError(str(exc)) from exc

                self._check_rate_limit(get_resp)

                if get_resp.status_code == 404:
                    self._sha_cache.pop(remote_path, None)
                    return
                sha = get_resp.json()["sha"]
                continue

            if response.status_code in (401, 403):
                raise StorageAuthError(f"GitHub 认证失败: {response.status_code}")

    async def load(self, remote_path: str) -> bytes:
        """Download file content via the raw media type."""
        try:
            response = await self._client.get(
                f"/repos/{self._repo}/contents/{remote_path}",
                params={"ref": self._branch},
                headers={"Accept": "application/vnd.github.raw+octet-stream"},
            )
        except httpx.TransportError as exc:
            raise StorageConnectionError(str(exc)) from exc

        self._check_rate_limit(response)

        if response.status_code == 200:
            return response.content
        if response.status_code == 404:
            raise FileNotFoundError(f"GitHub 上不存在该文件: {remote_path}")
        if response.status_code in (401, 403):
            raise StorageAuthError(f"GitHub 认证失败: {response.status_code}")
        if response.status_code in (413, 422):
            raise StorageFileSizeError(
                f"GitHub 拒绝下载 {remote_path}: HTTP {response.status_code}",
                max_size=_MAX_CONTENT_BYTES,
            )
        raise StorageConnectionError(
            f"GET {remote_path} 返回 {response.status_code}"
        )

    async def list(self, prefix: str) -> list[dict]:
        """List directory entries at prefix."""
        try:
            response = await self._client.get(
                f"/repos/{self._repo}/contents/{prefix}",
                params={"ref": self._branch},
            )
        except httpx.TransportError as exc:
            raise StorageConnectionError(str(exc)) from exc

        self._check_rate_limit(response)

        if response.status_code == 404:
            return []
        if response.status_code in (401, 403):
            raise StorageAuthError(f"GitHub 认证失败: {response.status_code}")
        if response.status_code != 200:
            raise StorageConnectionError(
                f"GET {prefix} 返回 {response.status_code}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            # A single file was requested rather than a directory.
            return [
                {
                    "path": payload.get("path", prefix),
                    "size": payload.get("size", 0),
                    "last_modified": None,
                }
            ]
        return [
            {
                "path": entry.get("path", ""),
                "size": entry.get("size", 0),
                "last_modified": None,
            }
            for entry in payload
        ]

    def get_url(self, remote_path: str) -> str:
        owner, repo_name = self._repo.split("/", 1)
        return f"https://raw.githubusercontent.com/{owner}/{repo_name}/{self._branch}/{remote_path}"

    async def aclose(self) -> None:
        await self._client.aclose()
