"""Safe command parser for skill installation — extracts identifiers without executing."""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote

_MAX_INPUT_LENGTH = 2048

_DANGEROUS_CHARS = frozenset(";|&$`\x00")

# Variant A: CLI commands
_CLI_RE = re.compile(
    r"(?:npx\s+skills\s+add|skillhub\s+install)\s+([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)",
    re.IGNORECASE,
)

# Variant B: GitHub URL
_GITHUB_RE = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)",
    re.IGNORECASE,
)

# Variant B: skills.sh URL
_SKILLS_SH_RE = re.compile(
    r"https?://skills\.sh/v1/skills/([a-zA-Z0-9_.-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParseResult:
    match_type: str  # 'cli' | 'url' | 'unmatched'
    provider: str | None
    skill_name: str | None
    repo_url: str | None
    raw_input: str


class SkillCommandParser:
    """Parses user input to extract skill identifiers safely."""

    def parse(self, raw_input: str) -> ParseResult:
        if not raw_input or not raw_input.strip():
            return ParseResult(
                match_type="unmatched",
                provider=None,
                skill_name=None,
                repo_url=None,
                raw_input=raw_input or "",
            )

        # Truncate to prevent DoS
        truncated = raw_input[:_MAX_INPUT_LENGTH]

        # Reject dangerous characters anywhere in the raw input (post-decode)
        decoded_input = unquote(truncated)
        normalized_input = unicodedata.normalize("NFKC", decoded_input)
        if any(c in _DANGEROUS_CHARS for c in normalized_input):
            return ParseResult(
                match_type="unmatched",
                provider=None,
                skill_name=None,
                repo_url=None,
                raw_input=truncated,
            )

        # Try variant A (CLI commands)
        match = _CLI_RE.search(truncated)
        if match:
            provider = match.group(1)
            skill_name = match.group(2)
            if self._validate_identifier(provider) and self._validate_identifier(skill_name):
                return ParseResult(
                    match_type="cli",
                    provider=provider.lower(),
                    skill_name=skill_name.lower(),
                    repo_url=None,
                    raw_input=truncated,
                )

        # Try variant B (GitHub URL)
        match = _GITHUB_RE.search(truncated)
        if match:
            provider = match.group(1)
            repo_name = match.group(2)
            if self._validate_identifier(provider) and self._validate_identifier(repo_name):
                return ParseResult(
                    match_type="url",
                    provider=provider.lower(),
                    skill_name=repo_name.lower(),
                    repo_url=f"https://github.com/{provider}/{repo_name}",
                    raw_input=truncated,
                )

        # Try variant B (skills.sh URL)
        match = _SKILLS_SH_RE.search(truncated)
        if match:
            skill_id = match.group(1)
            if self._validate_identifier(skill_id):
                return ParseResult(
                    match_type="url",
                    provider="skills.sh",
                    skill_name=skill_id.lower(),
                    repo_url=f"https://skills.sh/v1/skills/{skill_id}",
                    raw_input=truncated,
                )

        # No match — signal AI fallback
        return ParseResult(
            match_type="unmatched",
            provider=None,
            skill_name=None,
            repo_url=None,
            raw_input=truncated,
        )

    def _validate_identifier(self, value: str) -> bool:
        """Validate an extracted identifier for safety."""
        if not value:
            return False

        # URL-decode
        decoded = unquote(value)

        # Unicode normalize (NFKC)
        normalized = unicodedata.normalize("NFKC", decoded)

        # Length check
        if len(normalized) > 128:
            return False

        # Dangerous characters (post-decode)
        if any(c in _DANGEROUS_CHARS for c in normalized):
            return False

        # Path traversal (post-decode)
        if ".." in normalized or "/" in normalized or "\\" in normalized:
            return False

        return True
