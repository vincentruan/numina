"""GitHub Contents API storage backend."""
import base64

import httpx

from app.services.storage.base import (
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageRateLimitError,
)


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

    def _check_rate_limit(self, response: httpx.Response) -> None:
        if response.headers.get("x-ratelimit-remaining") == "0":
            reset_at = int(response.headers.get("x-ratelimit-reset", 0))
            raise StorageRateLimitError(reset_at=reset_at)

    async def save(self, content: bytes, filename: str, date_dir: str) -> str:
        remote_path = f"{date_dir}/{filename}"
        b64 = base64.b64encode(content).decode()

        for attempt in range(3):
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
                # Fetch current sha and retry
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
                # Re-fetch sha and retry once
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

    def get_url(self, remote_path: str) -> str:
        owner, repo_name = self._repo.split("/", 1)
        return f"https://raw.githubusercontent.com/{owner}/{repo_name}/{self._branch}/{remote_path}"

    async def aclose(self) -> None:
        await self._client.aclose()
