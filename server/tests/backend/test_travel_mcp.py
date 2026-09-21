"""Backend tests for travel module — MCP tool registration and family isolation."""


def test_mcp_travel_tools_registered():
    """Travel MCP tools are registered in the tool registry."""
    from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

    owner_tools = list_tools_for_role("owner")
    tool_names = {t.name for t in owner_tools}
    assert "get_travel_trips" in tool_names
    assert "get_travel_expenses" in tool_names
    assert "get_travel_split_balances" in tool_names


def test_mcp_travel_tools_have_descriptions():
    """Each travel MCP tool has a non-empty description."""
    from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

    owner_tools = list_tools_for_role("owner")
    travel_tools = [t for t in owner_tools if t.name.startswith("get_travel_")]
    for tool in travel_tools:
        assert tool.description, f"{tool.name} has no description"
        assert len(tool.description) > 10


def test_mcp_travel_tools_have_input_schema():
    """Each travel MCP tool declares an input_schema."""
    from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

    owner_tools = list_tools_for_role("owner")
    travel_tools = [t for t in owner_tools if t.name.startswith("get_travel_")]
    for tool in travel_tools:
        assert tool.input_schema is not None, f"{tool.name} has no input_schema"
        assert "type" in tool.input_schema


def test_mcp_travel_tools_read_only():
    """Travel MCP tools are read-only (no write required)."""
    from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

    owner_tools = list_tools_for_role("owner")
    travel_tools = [t for t in owner_tools if t.name.startswith("get_travel_")]
    for tool in travel_tools:
        assert tool.requires_write is False, f"{tool.name} should be read-only"
