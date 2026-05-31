"""System-level configuration loaded from project-root system-config.yaml.

Three-layer configuration model:
- ``.env`` / ``settings.py``      : environment-specific secrets and runtime params
- DB ``ai_providers``              : per-family user config (overrides system defaults)
- ``system-config.yaml`` (this)    : system metadata shared across environments;
                                     mutable by ops, requires service restart.

Layout:
    <project-root>/
    ├── .env
    ├── docker-compose.yml
    ├── system-config.yaml           # primary, committed to git (no secrets)
    └── system-config.local.yaml     # optional per-deployment override (gitignored)

Loader behaviour:
- Loaded once on first access; cached via lru_cache.
- Missing primary file → returns ``{}`` with a warning (does not block boot).
- Local override file deep-merges over primary when present.
- YAML parse error raises immediately (fail-fast at startup).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = "system-config.yaml"
_LOCAL_OVERRIDE_FILENAME = "system-config.local.yaml"


def _project_root() -> Path:
    """Walk up from this module to find the project root.

    Identified by the presence of ``docker-compose.yml`` (and absence of any
    parent that has it). Raises if not found within 8 levels.
    """
    cur = Path(__file__).resolve()
    for _ in range(8):
        if (cur / "docker-compose.yml").exists():
            return cur
        cur = cur.parent
    raise RuntimeError(
        "Cannot locate project root from "
        f"{Path(__file__).resolve()} (no docker-compose.yml within 8 levels)"
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge; override wins for non-dict leaves."""
    out: dict[str, Any] = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def get_system_config() -> dict[str, Any]:
    """Load system-config.yaml (with optional local override). Cached.

    Returns ``{}`` if the primary file is missing — this lets dev environments
    that haven't synced the file yet still boot. Production deployments should
    monitor logs for the warning.
    """
    root = _project_root()
    primary = root / _CONFIG_FILENAME
    override = root / _LOCAL_OVERRIDE_FILENAME

    if not primary.exists():
        logger.warning(
            "%s not found at %s; using empty system config", _CONFIG_FILENAME, primary
        )
        return {}

    with open(primary, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    if override.exists():
        with open(override, encoding="utf-8") as f:
            local: dict[str, Any] = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, local)
        logger.info("Loaded system config with local override from %s", override)

    return cfg


def get_max_tokens_default(model_id: str | None) -> int | None:
    """Resolve the default ``max_tokens`` for a given model_id by prefix match.

    Match is case-insensitive and order-sensitive (first hit wins, so longer
    prefixes must come earlier in ``system-config.yaml``).

    Returns:
        ``int`` when a prefix matches with a positive integer value.
        ``None`` when no prefix matches, model_id is empty, or the matched
        entry is malformed. Caller treats ``None`` as "no system default —
        let SDK / vendor decide".
    """
    if not model_id:
        return None
    cfg = get_system_config()
    table = (cfg.get("ai_models") or {}).get("max_tokens_defaults_by_prefix") or []
    low = model_id.lower()
    for entry in table:
        if not isinstance(entry, dict):
            continue
        prefix = (entry.get("prefix") or "").lower()
        if not prefix:
            continue
        if low.startswith(prefix):
            value = entry.get("max_tokens")
            if isinstance(value, int) and value > 0:
                return value
    return None
