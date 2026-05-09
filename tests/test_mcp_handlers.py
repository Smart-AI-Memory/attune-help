"""Direct unit tests for attune_help.mcp.handlers + mcp.server.

The existing ``test_mcp_server.py`` exercises handlers indirectly via
the server. This file targets the pieces that are easier to verify in
isolation: the ``_require_str`` validator, the engine builder error
paths, and the server-module factory + singleton.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from attune_help.mcp import server as server_mod
from attune_help.mcp.handlers import AttuneHelpHandlers, _require_str
from attune_help.mcp.server import (
    AttuneHelpMCPServer,
    _get_app,
    create_server,
)

# ---------------------------------------------------------------------------
# _require_str validator
# ---------------------------------------------------------------------------


def test_require_str_returns_value_when_present() -> None:
    value, err = _require_str({"topic": "auth"}, "topic")
    assert value == "auth"
    assert err is None


def test_require_str_errors_when_missing_required() -> None:
    value, err = _require_str({}, "topic")
    assert value is None
    assert err == {
        "success": False,
        "error": "topic is required and must be a string",
    }


def test_require_str_returns_none_for_missing_optional() -> None:
    value, err = _require_str({}, "topic", optional=True)
    assert value is None
    assert err is None


def test_require_str_errors_on_empty_string() -> None:
    value, err = _require_str({"topic": ""}, "topic")
    assert value is None
    assert err is not None
    assert err["success"] is False
    assert "topic" in err["error"]


def test_require_str_errors_on_non_string() -> None:
    value, err = _require_str({"topic": 42}, "topic")
    assert value is None
    assert err is not None
    assert err["success"] is False


def test_require_str_optional_rejects_empty_when_provided() -> None:
    value, err = _require_str({"topic": ""}, "topic", optional=True)
    assert value is None
    assert err is not None
    assert "when provided" in err["error"]


# ---------------------------------------------------------------------------
# AttuneHelpHandlers._engine path validation
# ---------------------------------------------------------------------------


def test_engine_uses_bundled_when_no_template_dir(tmp_path: Path) -> None:
    handlers = AttuneHelpHandlers(workspace_root=str(tmp_path))
    engine = handlers._engine(template_dir=None)
    assert engine is not None


def test_engine_validates_template_dir_against_workspace(tmp_path: Path) -> None:
    """Path traversal outside workspace_root must be rejected."""
    handlers = AttuneHelpHandlers(workspace_root=str(tmp_path))
    custom = tmp_path / "templates"
    custom.mkdir()
    # In-bounds path resolves cleanly.
    engine = handlers._engine(template_dir=str(custom))
    assert engine is not None


def test_engine_rejects_traversal_template_dir(tmp_path: Path) -> None:
    handlers = AttuneHelpHandlers(workspace_root=str(tmp_path))
    with pytest.raises(Exception):
        # Traversal attempts must surface as an error rather than
        # silently resolve outside the workspace.
        handlers._engine(template_dir="../../etc/passwd")


# ---------------------------------------------------------------------------
# server module factory + singleton
# ---------------------------------------------------------------------------


def test_create_server_returns_fresh_instance() -> None:
    a = create_server()
    b = create_server()
    assert isinstance(a, AttuneHelpMCPServer)
    assert isinstance(b, AttuneHelpMCPServer)
    # Factory yields separate objects each call.
    assert a is not b


def test_get_app_caches_singleton() -> None:
    # Reset the module-level cache so this test is self-contained.
    server_mod._app = None
    first = _get_app()
    second = _get_app()
    assert first is second
    server_mod._app = None  # restore for subsequent tests


def test_server_exposes_tools_dict() -> None:
    app = create_server()
    assert isinstance(app.tools, dict)
    assert app.tools, "server should register at least one tool"
    for name, defn in app.tools.items():
        assert name.startswith(
            "lookup_"
        ), f"tool {name!r} does not match the lookup_* prefix contract"
        assert "description" in defn or "input_schema" in defn


# ---------------------------------------------------------------------------
# Async dispatch — ensure call_tool wrapping handles unknown tools cleanly
# ---------------------------------------------------------------------------


def test_call_tool_unknown_tool_returns_error() -> None:
    """Server must not crash on an unknown tool name; should return an error dict."""
    app = create_server()
    result = asyncio.run(app.call_tool("not_a_tool", {}))
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "error" in result
