from typing import Any

WEB_SEARCH_PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "tavily": {
        "provider_class": "deerflow.community.tavily.tools:web_search_tool",
        "display_name": "Tavily Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://tavily.com",
        "note": "免费 1000 次/月",
    },
    "ddg_search": {
        "provider_class": "deerflow.community.ddg_search.tools:web_search_tool",
        "display_name": "DuckDuckGo",
        "requires_api_key": False,
        "config_fields": [
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://duckduckgo.com",
        "note": "免费无限制，无需 API Key",
    },
    "exa": {
        "provider_class": "deerflow.community.exa.tools:web_search_tool",
        "display_name": "Exa Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://exa.ai",
        "note": "语义搜索，适合研究类查询",
    },
    "serper": {
        "provider_class": "deerflow.community.serper.tools:web_search_tool",
        "display_name": "Serper (Google)",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://serper.dev",
        "note": "Google 搜索结果，免费 2500 次",
    },
    "firecrawl": {
        "provider_class": "deerflow.community.firecrawl.tools:web_search_tool",
        "display_name": "Firecrawl",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://firecrawl.dev",
        "note": "网页抓取 + 搜索",
    },
}


def get_provider_template(provider_name: str) -> dict[str, Any] | None:
    return WEB_SEARCH_PROVIDER_REGISTRY.get(provider_name)


def list_provider_templates() -> list[dict[str, Any]]:
    return [
        {"provider_name": name, **meta}
        for name, meta in WEB_SEARCH_PROVIDER_REGISTRY.items()
    ]


def reconcile_registry() -> list[str]:
    """启动时校验：检查已知 provider 的模块是否可导入。
    返回注册表中无法导入的 provider 名称列表（用于报警日志）。
    """
    import importlib
    import logging

    logger = logging.getLogger(__name__)
    unavailable: list[str] = []

    for name, meta in WEB_SEARCH_PROVIDER_REGISTRY.items():
        provider_class = meta.get("provider_class", "")
        module_path = provider_class.split(":")[0] if ":" in provider_class else ""
        if module_path:
            try:
                importlib.import_module(module_path)
            except ImportError:
                logger.warning(
                    "Web search provider '%s' module not importable: %s",
                    name,
                    module_path,
                )
                unavailable.append(name)

    return unavailable
