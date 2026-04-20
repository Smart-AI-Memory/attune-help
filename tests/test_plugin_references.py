"""MCP tool registry validation.

Verifies that registered MCP tool schemas and the server's
dispatch table stay in sync — every registered tool must
dispatch to a callable handler method.
"""

from __future__ import annotations


def _mcp_tool_names() -> set[str]:
    """Read the real tool registry from tool_schemas.py."""
    from attune_help.mcp.tool_schemas import get_tools

    return set(get_tools().keys())


class TestMcpToolReferences:
    """Every registered tool must follow the naming contract."""

    def test_lookup_tool_prefix_enforced(self) -> None:
        """All MCP tools must start with `lookup_` to avoid
        colliding with attune-ai's `help_*` tools when both
        servers are mounted in the same Claude Code session.
        """
        tools = _mcp_tool_names()
        assert tools, "No tools registered in tool_schemas.py"
        for name in tools:
            assert name.startswith("lookup_"), (
                f"Tool '{name}' missing required `lookup_` prefix "
                f"(collides with attune-ai's help_* tools otherwise)"
            )

    def test_expected_tool_names(self) -> None:
        """Lock the public tool surface so renames or accidental
        removals surface in CI rather than in a broken MCP session.
        """
        expected = {
            "lookup_topic",
            "lookup_list",
            "lookup_list_topics",
            "lookup_search",
            "lookup_suggest",
            "lookup_warn",
            "lookup_preamble",
            "lookup_reset",
            "lookup_simpler",
            "lookup_status",
        }
        assert _mcp_tool_names() == expected


class TestHandlerExistence:
    """Every registered tool must dispatch to a callable handler."""

    def test_all_tools_have_dispatch_entries(self) -> None:
        """Source of truth is the server's dispatch table — not
        method-name matching — because some tools intentionally
        map to differently-named handler methods.
        """
        from attune_help.mcp.server import AttuneHelpMCPServer

        server = AttuneHelpMCPServer()
        tools = _mcp_tool_names()

        for tool_name in tools:
            assert tool_name in server._dispatch, (
                f"Tool '{tool_name}' registered in tool_schemas but "
                f"has no dispatch entry in AttuneHelpMCPServer"
            )
            handler = server._dispatch[tool_name]
            assert callable(handler), f"Handler for '{tool_name}' is not callable"

    def test_no_orphan_dispatch_entries(self) -> None:
        """Dispatch table must not wire tools that aren't registered."""
        from attune_help.mcp.server import AttuneHelpMCPServer

        server = AttuneHelpMCPServer()
        tools = _mcp_tool_names()

        extra = set(server._dispatch.keys()) - tools
        assert not extra, f"Dispatch table wires tools not in tool_schemas: {sorted(extra)}"
