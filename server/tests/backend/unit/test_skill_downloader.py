"""Tests for skill downloader -- safe HTTP fetch of SKILL.md."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.backend.app.services.skill_command_parser import ParseResult
from apps.backend.app.services.skill_downloader import (
    DownloadResult,
    SkillDownloader,
    SkillDownloadError,
)

VALID_SKILL_MD = "---\nname: deploy-staging\ndescription: Deploy to staging\n---\n\n# Instructions\nDo stuff"
VALID_SKILL_MD_MASTER = "---\nname: deploy-staging\ndescription: Deploy via master\n---\n\n# Instructions\nDo other stuff"


def _make_github_cli_parse_result(
    provider: str = "anthropics",
    skill_name: str = "deploy-staging",
) -> ParseResult:
    return ParseResult(
        match_type="cli",
        provider=provider,
        skill_name=skill_name,
        repo_url=None,
        raw_input=f"npx skills add {provider}/{skill_name}",
    )


def _make_github_url_parse_result(
    provider: str = "anthropics",
    skill_name: str = "skills",
) -> ParseResult:
    return ParseResult(
        match_type="url",
        provider=provider,
        skill_name=skill_name,
        repo_url=f"https://github.com/{provider}/{skill_name}",
        raw_input=f"https://github.com/{provider}/{skill_name}",
    )


def _make_skills_sh_parse_result(
    skill_name: str = "deploy-staging",
) -> ParseResult:
    return ParseResult(
        match_type="url",
        provider="skills.sh",
        skill_name=skill_name,
        repo_url=f"https://skills.sh/v1/skills/{skill_name}",
        raw_input=f"https://skills.sh/v1/skills/{skill_name}",
    )


def _mock_response(
    status_code: int = 200,
    text: str = "",
    headers: dict | None = None,
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.headers = httpx.Headers(headers or {})
    return resp


@pytest.fixture
def downloader():
    return SkillDownloader()


class TestGitHubHappyPath:
    @pytest.mark.asyncio
    async def test_github_main_branch_success(self, downloader):
        """Mock GitHub raw URL (main branch) returns valid SKILL.md."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(status_code=200, text=VALID_SKILL_MD)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert isinstance(result, DownloadResult)
        assert result.content == VALID_SKILL_MD
        assert result.source_url == "https://github.com/anthropics/deploy-staging"
        assert result.skill_id == "deploy-staging"
        # Should have tried the main branch URL
        call_url = mock_client.get.call_args[0][0]
        assert "/main/" in call_url

    @pytest.mark.asyncio
    async def test_github_url_type_success(self, downloader):
        """GitHub URL parse result also works."""
        parse_result = _make_github_url_parse_result()
        mock_resp = _mock_response(status_code=200, text=VALID_SKILL_MD)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert result.content == VALID_SKILL_MD
        assert result.skill_id == "skills"


class TestSkillsShHappyPath:
    @pytest.mark.asyncio
    async def test_skills_sh_success(self, downloader):
        """Mock skills.sh URL returns valid SKILL.md."""
        parse_result = _make_skills_sh_parse_result()
        mock_resp = _mock_response(status_code=200, text=VALID_SKILL_MD)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert isinstance(result, DownloadResult)
        assert result.content == VALID_SKILL_MD
        assert result.source_url == "https://skills.sh/v1/skills/deploy-staging/SKILL.md"
        assert result.skill_id == "deploy-staging"
        # Verify the URL constructed
        call_url = mock_client.get.call_args[0][0]
        assert call_url == "https://skills.sh/v1/skills/deploy-staging/SKILL.md"


class TestGitHubFallback:
    @pytest.mark.asyncio
    async def test_main_404_master_success(self, downloader):
        """GitHub 404 on main branch, success on master fallback."""
        parse_result = _make_github_cli_parse_result()
        resp_404 = _mock_response(status_code=404)
        resp_200 = _mock_response(status_code=200, text=VALID_SKILL_MD_MASTER)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[resp_404, resp_200])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert result.content == VALID_SKILL_MD_MASTER
        # Two GET calls: main then master
        assert mock_client.get.call_count == 2
        first_url = mock_client.get.call_args_list[0][0][0]
        second_url = mock_client.get.call_args_list[1][0][0]
        assert "/main/" in first_url
        assert "/master/" in second_url

    @pytest.mark.asyncio
    async def test_main_and_master_both_404(self, downloader):
        """Both main and master branches return 404."""
        parse_result = _make_github_cli_parse_result()
        resp_404_a = _mock_response(status_code=404)
        resp_404_b = _mock_response(status_code=404)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[resp_404_a, resp_404_b])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="404"):
            await downloader.download(parse_result)


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_descriptive_error(self, downloader):
        """HTTP timeout raises SkillDownloadError with description."""
        parse_result = _make_github_cli_parse_result()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.ReadTimeout("read timeout")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="[Tt]imeout"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_connect_timeout_raises_descriptive_error(self, downloader):
        """Connect timeout raises SkillDownloadError with description."""
        parse_result = _make_github_cli_parse_result()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectTimeout("connect timeout")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="[Tt]imeout"):
            await downloader.download(parse_result)


class TestResponseSizeLimit:
    @pytest.mark.asyncio
    async def test_response_exceeds_1mb_rejected(self, downloader):
        """Response body > 1MB is rejected with size error."""
        parse_result = _make_github_cli_parse_result()
        large_text = "x" * (1 * 1024 * 1024 + 1)
        mock_resp = _mock_response(status_code=200, text=large_text)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="too large"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_content_length_header_exceeds_1mb_rejected(self, downloader):
        """Content-Length header > 1MB is rejected before reading body."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(
            status_code=200,
            text="small",
            headers={"content-length": str(2 * 1024 * 1024)},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="too large"):
            await downloader.download(parse_result)


class TestInvalidContent:
    @pytest.mark.asyncio
    async def test_no_frontmatter_raises_validation_error(self, downloader):
        """Response without valid frontmatter raises validation error."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(
            status_code=200, text="just plain text, no frontmatter"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="not a valid SKILL.md"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_frontmatter_without_name_raises_validation_error(self, downloader):
        """Frontmatter missing name field raises validation error."""
        parse_result = _make_github_cli_parse_result()
        content = "---\ndescription: no name field\n---\n\nbody"
        mock_resp = _mock_response(status_code=200, text=content)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="not a valid SKILL.md"):
            await downloader.download(parse_result)


class TestNon200Status:
    @pytest.mark.asyncio
    async def test_500_raises_descriptive_error(self, downloader):
        """Non-200 status code raises descriptive error."""
        parse_result = _make_skills_sh_parse_result()
        mock_resp = _mock_response(status_code=500)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="HTTP 500"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_403_raises_descriptive_error(self, downloader):
        """403 status raises descriptive error."""
        parse_result = _make_skills_sh_parse_result()
        mock_resp = _mock_response(status_code=403)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="HTTP 403"):
            await downloader.download(parse_result)


class TestRedirectRejection:
    @pytest.mark.asyncio
    async def test_301_redirect_rejected(self, downloader):
        """301 redirect response is rejected (SSRF prevention)."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(
            status_code=301,
            headers={"location": "http://169.254.169.254/metadata"},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="[Rr]edirect"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_302_redirect_rejected(self, downloader):
        """302 redirect response is rejected (SSRF prevention)."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(
            status_code=302,
            headers={"location": "http://10.0.0.1/internal"},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="[Rr]edirect"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_307_redirect_rejected(self, downloader):
        """307 redirect response is rejected (SSRF prevention)."""
        parse_result = _make_github_cli_parse_result()
        mock_resp = _mock_response(
            status_code=307,
            headers={"location": "http://evil.com/steal"},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(SkillDownloadError, match="[Rr]edirect"):
            await downloader.download(parse_result)


class TestHostAllowlist:
    @pytest.mark.asyncio
    async def test_disallowed_host_rejected(self, downloader):
        """URL with disallowed host is rejected before fetch."""
        _parse_result = ParseResult(
            match_type="url",
            provider="evil",
            skill_name="test",
            repo_url="https://evil.com/test",
            raw_input="https://evil.com/test",
        )
        # The downloader builds a GitHub-style URL with the 'evil' provider,
        # which resolves to raw.githubusercontent.com (allowed).
        # To test host allowlist directly, call _validate_host.
        with pytest.raises(SkillDownloadError, match="not in allowlist"):
            downloader._validate_host("https://evil.com/skills/test/SKILL.md")

    @pytest.mark.asyncio
    async def test_localhost_rejected(self, downloader):
        """localhost URLs are rejected."""
        with pytest.raises(SkillDownloadError, match="not in allowlist"):
            downloader._validate_host("http://localhost:8080/secret")

    @pytest.mark.asyncio
    async def test_internal_ip_rejected(self, downloader):
        """Internal IP URLs are rejected."""
        with pytest.raises(SkillDownloadError, match="not in allowlist"):
            downloader._validate_host("http://169.254.169.254/metadata")

    @pytest.mark.asyncio
    async def test_allowed_hosts_pass(self, downloader):
        """Allowed hosts pass validation without error."""
        downloader._validate_host("https://raw.githubusercontent.com/anthropics/skills/main/skills/test/SKILL.md")
        downloader._validate_host("https://skills.sh/v1/skills/test/SKILL.md")


class TestUnmatchedParseResult:
    @pytest.mark.asyncio
    async def test_unmatched_raises_error(self, downloader):
        """Unmatched parse result raises error immediately."""
        parse_result = ParseResult(
            match_type="unmatched",
            provider=None,
            skill_name=None,
            repo_url=None,
            raw_input="random text",
        )
        with pytest.raises(SkillDownloadError, match="unmatched"):
            await downloader.download(parse_result)


class TestSkillIdExtraction:
    @pytest.mark.asyncio
    async def test_skill_id_from_skill_name(self, downloader):
        """skill_id is derived from skill_name with spaces replaced by hyphens."""
        # Note: the parser already lowercases skill_name, but test the downloader's
        # own skill_id derivation logic
        parse_result = _make_skills_sh_parse_result(skill_name="my-cool-skill")
        mock_resp = _mock_response(status_code=200, text=VALID_SKILL_MD)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert result.skill_id == "my-cool-skill"

    @pytest.mark.asyncio
    async def test_skill_id_spaces_replaced_with_hyphens(self, downloader):
        """Spaces in skill_name are replaced with hyphens in skill_id."""
        parse_result = _make_skills_sh_parse_result(skill_name="my cool skill")
        # Override skill_name to contain spaces for this test
        content = "---\nname: my-cool-skill\ndescription: test\n---\n\nbody"
        mock_resp = _mock_response(status_code=200, text=content)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await downloader.download(parse_result)

        assert result.skill_id == "my-cool-skill"


class TestMissingProviderOrSkillName:
    @pytest.mark.asyncio
    async def test_no_skill_name_raises_error(self, downloader):
        """Missing skill_name raises error during candidate building."""
        parse_result = ParseResult(
            match_type="cli",
            provider="anthropics",
            skill_name=None,
            repo_url=None,
            raw_input="test",
        )
        with pytest.raises(SkillDownloadError, match="No skill name"):
            await downloader.download(parse_result)

    @pytest.mark.asyncio
    async def test_no_provider_for_github_raises_error(self, downloader):
        """Missing provider for GitHub-style source raises error."""
        parse_result = ParseResult(
            match_type="cli",
            provider=None,
            skill_name="test-skill",
            repo_url=None,
            raw_input="test",
        )
        with pytest.raises(SkillDownloadError, match="No provider"):
            await downloader.download(parse_result)


class TestHttpClientConfig:
    @pytest.mark.asyncio
    async def test_follow_redirects_false(self, downloader):
        """Verify AsyncClient is created with follow_redirects=False."""
        parse_result = _make_skills_sh_parse_result()
        mock_resp = _mock_response(status_code=200, text=VALID_SKILL_MD)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.backend.app.services.skill_downloader.httpx.AsyncClient",
            return_value=mock_client,
        ) as mock_ctor:
            await downloader.download(parse_result)
            mock_ctor.assert_called_once()
            call_kwargs = mock_ctor.call_args[1]
            assert call_kwargs["follow_redirects"] is False
