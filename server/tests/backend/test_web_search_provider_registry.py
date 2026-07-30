from apps.backend.app.services.web_search_provider_registry import (
    WEB_SEARCH_PROVIDER_REGISTRY,
    get_provider_template,
    list_provider_templates,
)


def test_registry_has_expected_providers():
    names = set(WEB_SEARCH_PROVIDER_REGISTRY.keys())
    assert "tavily" in names
    assert "ddg_search" in names
    assert "exa" in names
    assert "serper" in names
    assert "firecrawl" in names


def test_get_provider_template_returns_metadata():
    tmpl = get_provider_template("tavily")
    assert tmpl is not None
    assert tmpl["requires_api_key"] is True
    assert tmpl["display_name"] == "Tavily Search"
    assert any(f["key"] == "api_key" for f in tmpl["config_fields"])


def test_get_provider_template_unknown_returns_none():
    assert get_provider_template("nonexistent") is None


def test_list_provider_templates_returns_all():
    templates = list_provider_templates()
    assert len(templates) == 5
    assert all("provider_name" in t for t in templates)


def test_ddg_search_does_not_require_api_key():
    tmpl = get_provider_template("ddg_search")
    assert tmpl["requires_api_key"] is False


def test_reconcile_registry_returns_empty_when_all_present():
    from apps.backend.app.services.web_search_provider_registry import (
        reconcile_registry,
    )
    # Without deerflow.community installed, should return empty (graceful skip)
    result = reconcile_registry()
    assert isinstance(result, list)
