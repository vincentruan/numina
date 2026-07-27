"""Skill downloader -- safe HTTP fetch of SKILL.md from GitHub or skills.sh."""

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from apps.backend.app.services.skill_command_parser import ParseResult
from apps.backend.app.services.skill_parser import validate_skill_content

_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB

_ALLOWED_HOSTS = frozenset(
    {
        "raw.githubusercontent.com",
        "skills.sh",
    }
)

_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=10.0, pool=10.0)

_GITHUB_BRANCHES = ("main", "master")


class SkillDownloadError(Exception):
    """Raised when skill download fails."""


@dataclass(frozen=True)
class DownloadResult:
    """Result of a successful SKILL.md download."""

    content: str
    source_url: str
    skill_id: str


class SkillDownloader:
    """Downloads SKILL.md from GitHub or skills.sh with security controls.

    Security features:
    - Host allowlist (raw.githubusercontent.com, skills.sh only)
    - No automatic redirect following (SSRF prevention)
    - 3xx responses rejected explicitly
    - 1 MB max response size
    - Content validation via validate_skill_content()
    """

    def _build_candidates(self, parse_result: ParseResult) -> list[tuple[str, str]]:
        """Build candidate (fetch_url, source_url) pairs to try sequentially.

        For GitHub: tries 'main' then 'master' branch.
        For skills.sh: single URL.
        """
        skill_name = parse_result.skill_name
        if not skill_name:
            raise SkillDownloadError("No skill name in parse result")

        if parse_result.provider == "skills.sh":
            url = f"https://skills.sh/v1/skills/{skill_name}/SKILL.md"
            return [(url, url)]

        # GitHub-style: provider/skill_name repo
        provider = parse_result.provider
        if not provider:
            raise SkillDownloadError("No provider in parse result")

        candidates: list[tuple[str, str]] = []
        for branch in _GITHUB_BRANCHES:
            fetch_url = (
                f"https://raw.githubusercontent.com/{provider}/{skill_name}"
                f"/{branch}/skills/{skill_name}/SKILL.md"
            )
            source_url = f"https://github.com/{provider}/{skill_name}"
            candidates.append((fetch_url, source_url))
        return candidates

    @staticmethod
    def _validate_host(url: str) -> None:
        """Reject URLs whose host is not in the allowlist."""
        host = urlparse(url).hostname
        if host not in _ALLOWED_HOSTS:
            raise SkillDownloadError(f"Host '{host}' not in allowlist")

    async def _safe_get(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Fetch a single URL with security checks.

        Returns the response text on success, None for 404.
        Raises SkillDownloadError on security violations or HTTP errors.
        """
        self._validate_host(url)

        response = await client.get(url)

        # SSRF prevention: reject redirects explicitly
        if 300 <= response.status_code < 400:
            raise SkillDownloadError(
                f"Redirect detected (status {response.status_code}) -- "
                "automatic redirects are disabled for security"
            )

        # 404 returns None so caller can try fallback
        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise SkillDownloadError(f"HTTP {response.status_code} fetching {url}")

        # Size check via Content-Length header
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_RESPONSE_BYTES:
                    raise SkillDownloadError(
                        f"Response too large: Content-Length {content_length} "
                        f"exceeds {_MAX_RESPONSE_BYTES} bytes"
                    )
            except ValueError:
                pass  # Malformed Content-Length; body-size check still applies

        content = response.text

        # Size check on actual body
        if len(content.encode("utf-8")) > _MAX_RESPONSE_BYTES:
            raise SkillDownloadError(
                f"Response too large: body exceeds {_MAX_RESPONSE_BYTES} bytes"
            )

        return content

    async def download(self, parse_result: ParseResult) -> DownloadResult:
        """Download SKILL.md from the appropriate source.

        For GitHub sources, tries 'main' branch first, then 'master' fallback.
        For skills.sh, fetches directly.
        """
        if parse_result.match_type == "unmatched":
            raise SkillDownloadError("Cannot download for unmatched parse result")

        candidates = self._build_candidates(parse_result)
        raw_skill_name = parse_result.skill_name
        if raw_skill_name is None:
            raise SkillDownloadError("parse_result.skill_name is None")
        skill_id = raw_skill_name.replace(" ", "-")

        last_error: SkillDownloadError | None = None

        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=False,
        ) as client:
            for fetch_url, source_url in candidates:
                try:
                    content = await self._safe_get(client, fetch_url)
                except httpx.TimeoutException as exc:
                    raise SkillDownloadError(
                        f"Timeout fetching {fetch_url}: {exc}"
                    ) from exc
                except httpx.HTTPError as exc:
                    raise SkillDownloadError(
                        f"HTTP error fetching {fetch_url}: {exc}"
                    ) from exc

                if content is None:
                    # 404 -- try next candidate (e.g. master branch fallback)
                    last_error = SkillDownloadError(f"HTTP 404 fetching {fetch_url}")
                    continue

                # Validate downloaded content
                if not validate_skill_content(content):
                    raise SkillDownloadError(
                        f"Downloaded content from {fetch_url} "
                        "is not a valid SKILL.md (missing frontmatter with name)"
                    )

                return DownloadResult(
                    content=content,
                    source_url=source_url,
                    skill_id=skill_id,
                )

        # All candidates exhausted
        raise last_error or SkillDownloadError("All download attempts failed")
