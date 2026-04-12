"""MCP server tests for attune-help.

Tests the AttuneHelpMCPServer class directly (no stdio
transport), verifying tool registration, dispatch, handler
behavior, and path validation.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from attune_help.mcp.handlers import AttuneHelpHandlers
from attune_help.mcp.path_validation import validate_file_path
from attune_help.mcp.server import AttuneHelpMCPServer

# -- Server construction ---------------------------------------------


class TestServerConstruction:
    """Basic construction and registration."""

    def test_default_workspace_is_cwd(self) -> None:
        import os

        server = AttuneHelpMCPServer()
        assert server._workspace_root == os.getcwd()

    def test_custom_workspace(self, tmp_path: Path) -> None:
        server = AttuneHelpMCPServer(workspace_root=str(tmp_path))
        assert server._workspace_root == str(tmp_path)

    def test_tool_count_matches_dispatch(self) -> None:
        """Tool count must match the dispatch table size.

        Use the dispatch table as the source of truth instead
        of a hardcoded number so adding a new tool doesn't
        force a mechanical test update. See the error template
        `mcp-tool-count-tests-are-hardcoded.md` for the
        history behind this change.
        """
        server = AttuneHelpMCPServer()
        assert len(server.tools) == len(server._dispatch)
        assert len(server.tools) >= 9  # lower bound: current set

    def test_all_tools_have_lookup_prefix(self) -> None:
        server = AttuneHelpMCPServer()
        for name in server.tools:
            assert name.startswith("lookup_"), name

    def test_dispatch_keys_match_tools(self) -> None:
        server = AttuneHelpMCPServer()
        assert set(server._dispatch.keys()) == set(server.tools.keys())


# -- Tool schemas ----------------------------------------------------


class TestToolSchemas:
    """Each tool must have name, description, inputSchema."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "lookup_topic",
            "lookup_list",
            "lookup_warn",
            "lookup_preamble",
            "lookup_reset",
            "lookup_status",
        ],
    )
    def test_tool_has_description_and_schema(self, tool_name: str) -> None:
        server = AttuneHelpMCPServer()
        defn = server.tools[tool_name]
        assert "description" in defn
        assert isinstance(defn["description"], str)
        assert len(defn["description"]) > 10
        assert "input_schema" in defn
        assert defn["input_schema"]["type"] == "object"


# -- lookup_topic ----------------------------------------------------


class TestLookupTopic:
    """Handler-level tests for lookup_topic."""

    def test_bundled_topic_returns_success(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-{int(time.time() * 1000000)}"
        r = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        assert r["success"], r
        assert r["rendered"], "rendered content should be non-empty"
        assert r["depth_level"] == 0
        assert isinstance(r["tags"], list)

    def test_lookup_topic_does_not_double_advance(self) -> None:
        """Regression: handler must advance the session exactly once per call.

        The original implementation called both ``engine.lookup_raw()`` and
        ``engine.lookup()`` on the same topic. Both methods advance the
        session state via ``populate_progressive``, so one handler call
        advanced the session twice. Fix: render the ``PopulatedTemplate``
        returned by the first call via ``engine.render(raw)`` — no
        double-advance.

        This test asserts two things directly against the underlying session
        storage, independent of which topic is used or how many depth levels
        it has:

        1. After exactly one successful handler call on a fresh session, the
           stored ``depth_level`` must be 0 (the concept view). If the bug
           comes back, ``depth_level`` will be 1 or higher after a single
           call because ``engine.lookup()`` ran a second ``populate_progressive``.
        2. The ``rendered`` field returned to the caller must match the
           content of the template whose depth the session records, not the
           next-depth template that a second advance would pick up.

        If this test starts failing, check ``handlers.lookup_topic`` — someone
        has re-added a second ``lookup()`` / ``lookup_raw()`` call after the
        initial ``engine.lookup_raw(topic)``.
        """
        from attune_help.storage import LocalFileStorage

        server = AttuneHelpMCPServer()
        uid = f"test-no-double-advance-{int(time.time() * 1000000)}"

        # Fresh session: nothing stored yet.
        storage = LocalFileStorage()
        pre_call_session = storage.get_session(uid)
        assert (
            pre_call_session.get("depth_level", 0) == 0
        ), f"session for {uid} was not fresh: {pre_call_session}"

        result = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        assert result["success"], result
        assert result["depth_level"] == 0, (
            f"handler returned depth_level={result['depth_level']}, expected 0 "
            "— the first call must return the concept view, not a deeper level"
        )

        # The authoritative check: after one handler call, the session
        # storage must record exactly depth 0. Double-advancing would push
        # this to 1 (or higher if the topic had more depth templates).
        post_call_session = storage.get_session(uid)
        assert post_call_session.get("depth_level") == 0, (
            f"session advanced to depth_level={post_call_session.get('depth_level')} "
            f"after a single handler call, expected 0. Full session: "
            f"{post_call_session}. This means handlers.lookup_topic is calling "
            "populate_progressive more than once per request — the double-advance "
            "bug is back."
        )
        assert post_call_session.get("last_topic") == "bug-predict", (
            f"session last_topic={post_call_session.get('last_topic')}, " "expected 'bug-predict'"
        )

    def test_missing_topic_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_topic", {}))
        assert not r["success"]
        assert "topic is required" in r["error"]

    def test_unknown_topic_returns_error(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-{int(time.time() * 1000000)}"
        r = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "definitely-not-a-real-topic-xyz", "user_id": uid},
            )
        )
        assert not r["success"]
        assert "not found" in r["error"].lower()

    def test_invalid_renderer_rejected(self) -> None:
        """Schema declares a renderer enum; handler enforces it too."""
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "renderer": "not-a-real-renderer"},
            )
        )
        assert not r["success"]
        assert "renderer must be one of" in r["error"]
        assert "not-a-real-renderer" in r["error"]

    def test_all_schema_renderers_accepted(self) -> None:
        """Every renderer the schema declares must be accepted."""
        server = AttuneHelpMCPServer()
        schema_enum = server.tools["lookup_topic"]["input_schema"]["properties"]["renderer"]["enum"]
        for renderer in schema_enum:
            uid = f"test-renderer-{renderer}-{int(time.time() * 1000000)}"
            r = asyncio.run(
                server.call_tool(
                    "lookup_topic",
                    {
                        "topic": "bug-predict",
                        "user_id": uid,
                        "renderer": renderer,
                    },
                )
            )
            assert r["success"], f"renderer={renderer!r} rejected by handler: {r}"

    def test_renderer_allowlist_derives_from_engine(self) -> None:
        """Schema enum and handler allowlist must track engine.VALID_RENDERERS.

        Drift guard: adding a renderer to HelpEngine without
        updating MCP schemas used to require a manual edit in
        three places. Now they all derive from one source —
        this test fails loudly if someone re-introduces a
        hardcoded list.
        """
        from attune_help.engine import VALID_RENDERERS
        from attune_help.mcp.handlers import _VALID_RENDERERS

        # Handler allowlist = engine - {"auto"} (auto is
        # meaningless across a protocol boundary).
        assert _VALID_RENDERERS == VALID_RENDERERS - {"auto"}

        server = AttuneHelpMCPServer()
        schema_enum = set(
            server.tools["lookup_topic"]["input_schema"]["properties"]["renderer"]["enum"]
        )
        assert schema_enum == _VALID_RENDERERS

    def test_json_renderer_accepted(self) -> None:
        """Regression: v0.4.0 added the `json` renderer to
        the engine but forgot to propagate it to the MCP layer."""
        server = AttuneHelpMCPServer()
        uid = f"test-json-renderer-{int(time.time() * 1000000)}"
        r = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {
                    "topic": "bug-predict",
                    "user_id": uid,
                    "renderer": "json",
                },
            )
        )
        assert r["success"], r
        import json as _json

        payload = _json.loads(r["rendered"])
        assert "template_id" in payload
        assert "sections" in payload


# -- lookup_list -----------------------------------------------------


class TestLookupList:
    """Handler-level tests for lookup_list."""

    def test_no_filter_returns_many(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list", {}))
        assert r["success"], r
        assert r["total"] >= 40, f"expected ≥40 topics, got {r['total']}"
        assert isinstance(r["categories"], dict)
        assert len(r["categories"]) > 0

    def test_tag_filter_narrows(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list", {"tag": "python", "limit": 10}))
        assert r["success"], r
        assert r["shown"] <= 10

    def test_unknown_tag_returns_empty(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_list",
                {"tag": "definitely-not-a-real-tag-xyz"},
            )
        )
        assert r["success"], r
        assert r["total"] == 0


# -- lookup_warn -----------------------------------------------------


class TestLookupWarn:
    """Handler-level tests for lookup_warn."""

    def test_python_file_returns_warnings(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_warn",
                {"file_path": "src/app.py", "max_results": 3},
            )
        )
        assert r["success"], r
        assert r["count"] >= 0
        assert isinstance(r["warnings"], list)

    def test_missing_file_path_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_warn", {}))
        assert not r["success"]
        assert "file_path is required" in r["error"]

    def test_null_byte_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_warn", {"file_path": "foo\x00.py"}))
        assert not r["success"]
        assert "null" in r["error"].lower()


# -- lookup_preamble -------------------------------------------------


class TestLookupPreamble:
    """Handler-level tests for lookup_preamble."""

    def test_missing_feature_name_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_preamble", {}))
        assert not r["success"]
        assert "feature_name is required" in r["error"]

    def test_unknown_feature_returns_error(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_preamble",
                {"feature_name": "definitely-not-a-feature"},
            )
        )
        assert not r["success"]


# -- lookup_reset ----------------------------------------------------


class TestLookupReset:
    """Handler-level tests for lookup_reset."""

    def test_reset_succeeds(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-reset-{int(time.time() * 1000000)}"
        r = asyncio.run(server.call_tool("lookup_reset", {"user_id": uid}))
        assert r["success"], r
        assert r["user_id"] == uid
        assert r["topic"] is None

    def test_empty_user_id_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_reset", {"user_id": ""}))
        assert not r["success"]

    def test_reset_single_topic_preserves_others(self) -> None:
        """Resetting one topic must not clear other topics."""
        from attune_help.storage import LocalFileStorage

        server = AttuneHelpMCPServer()
        uid = f"test-reset-single-{int(time.time() * 1000000)}"

        # Seed two topics into the session.
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "code-quality", "user_id": uid},
            )
        )
        mid = LocalFileStorage().get_session(uid)
        assert "bug-predict" in mid["topics"]
        assert "code-quality" in mid["topics"]

        # Reset one topic only.
        r = asyncio.run(
            server.call_tool(
                "lookup_reset",
                {"user_id": uid, "topic": "bug-predict"},
            )
        )
        assert r["success"], r
        assert r["topic"] == "bug-predict"

        after = LocalFileStorage().get_session(uid)
        assert "bug-predict" not in after["topics"]
        assert "code-quality" in after["topics"]

    def test_reset_all_clears_topics_map(self) -> None:
        """Reset without a topic must clear the full per-topic map."""
        from attune_help.storage import LocalFileStorage

        server = AttuneHelpMCPServer()
        uid = f"test-reset-all-{int(time.time() * 1000000)}"
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        asyncio.run(server.call_tool("lookup_reset", {"user_id": uid}))
        after = LocalFileStorage().get_session(uid)
        assert after["topics"] == {}
        assert after["order"] == []
        assert after["last_topic"] is None

    def test_reset_rejects_empty_topic(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_reset",
                {"user_id": "x", "topic": ""},
            )
        )
        assert not r["success"]
        assert "topic" in r["error"]


# -- lookup_status ---------------------------------------------------


class TestLookupStatus:
    """Handler-level tests for lookup_status."""

    def test_fresh_session_reports_depth_zero(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-status-fresh-{int(time.time() * 1000000)}"
        r = asyncio.run(server.call_tool("lookup_status", {"user_id": uid}))
        assert r["success"], r
        assert r["user_id"] == uid
        assert r["depth_level"] == 0
        assert r["level_label"] == "concept"
        assert r["last_topic"] is None

    def test_status_reflects_prior_lookup(self) -> None:
        """After a lookup_topic call, status should show that topic."""
        server = AttuneHelpMCPServer()
        uid = f"test-status-after-lookup-{int(time.time() * 1000000)}"

        # Seed the session with one lookup.
        lookup_result = asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        assert lookup_result["success"], lookup_result

        status = asyncio.run(server.call_tool("lookup_status", {"user_id": uid}))
        assert status["success"], status
        assert status["last_topic"] == "bug-predict"
        assert status["depth_level"] == 0
        assert status["level_label"] == "concept"

    def test_status_is_read_only(self) -> None:
        """Calling lookup_status must NOT advance the session."""
        from attune_help.storage import LocalFileStorage

        server = AttuneHelpMCPServer()
        uid = f"test-status-readonly-{int(time.time() * 1000000)}"

        # Seed with a lookup so there's real state to read.
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )

        before = LocalFileStorage().get_session(uid)

        # Call status several times — depth must not move.
        for _ in range(3):
            r = asyncio.run(server.call_tool("lookup_status", {"user_id": uid}))
            assert r["success"], r

        after = LocalFileStorage().get_session(uid)
        assert before.get("depth_level") == after.get("depth_level"), (
            f"lookup_status advanced the session: {before} → {after}. "
            "This tool MUST be read-only."
        )
        assert before.get("last_topic") == after.get("last_topic")

    def test_empty_user_id_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_status", {"user_id": ""}))
        assert not r["success"]

    def test_status_returns_topics_map(self) -> None:
        """Status must expose the per-topic dict + LRU order
        so clients can render a full session view."""
        server = AttuneHelpMCPServer()
        uid = f"test-status-topics-{int(time.time() * 1000000)}"

        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "bug-predict", "user_id": uid},
            )
        )
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "code-quality", "user_id": uid},
            )
        )

        r = asyncio.run(server.call_tool("lookup_status", {"user_id": uid}))
        assert r["success"], r
        assert "topics" in r
        assert "order" in r
        assert "bug-predict" in r["topics"]
        assert "code-quality" in r["topics"]
        assert r["order"][-1] == "code-quality"

    def test_fresh_session_has_empty_topics_map(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-status-empty-{int(time.time() * 1000000)}"
        r = asyncio.run(server.call_tool("lookup_status", {"user_id": uid}))
        assert r["success"], r
        assert r["topics"] == {}
        assert r["order"] == []


# -- lookup_simpler (T4) ---------------------------------------------


class TestLookupSimplerMCP:
    """Handler-level tests for lookup_simpler."""

    def test_simpler_steps_down_after_climb(self) -> None:
        """Climb to depth 2, then simpler should return to depth 1."""
        server = AttuneHelpMCPServer()
        uid = f"test-simpler-{int(time.time() * 1000000)}"

        for _ in range(3):
            r = asyncio.run(
                server.call_tool(
                    "lookup_topic",
                    {"topic": "security-audit", "user_id": uid},
                )
            )
            assert r["success"], r
        assert r["depth_level"] == 2

        r = asyncio.run(
            server.call_tool(
                "lookup_simpler",
                {"topic": "security-audit", "user_id": uid},
            )
        )
        assert r["success"], r
        assert r["topic"] == "security-audit"
        assert r["depth_level"] == 1
        assert r["rendered"]

    def test_simpler_clamps_at_zero(self) -> None:
        server = AttuneHelpMCPServer()
        uid = f"test-simpler-zero-{int(time.time() * 1000000)}"
        asyncio.run(
            server.call_tool(
                "lookup_topic",
                {"topic": "security-audit", "user_id": uid},
            )
        )
        r = asyncio.run(
            server.call_tool(
                "lookup_simpler",
                {"topic": "security-audit", "user_id": uid},
            )
        )
        assert r["success"], r
        assert r["depth_level"] == 0

    def test_simpler_missing_topic_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_simpler", {}))
        assert not r["success"]
        assert "topic is required" in r["error"]

    def test_simpler_unknown_topic_returns_error(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_simpler",
                {"topic": "definitely-not-real-xyz"},
            )
        )
        assert not r["success"]

    def test_simpler_invalid_renderer_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(
            server.call_tool(
                "lookup_simpler",
                {"topic": "security-audit", "renderer": "bogus"},
            )
        )
        assert not r["success"]
        assert "renderer must be one of" in r["error"]


# -- Discovery tools (T3) --------------------------------------------


class TestListTopicsMCP:
    """Handler-level tests for list_topics."""

    def test_no_filter_returns_topics(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list_topics", {}))
        assert r["success"], r
        assert r["count"] > 0
        assert isinstance(r["topics"], list)

    def test_type_filter(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list_topics", {"type": "concepts"}))
        assert r["success"], r
        assert r["type_filter"] == "concepts"
        assert r["count"] > 0

    def test_limit_applied(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list_topics", {"limit": 3}))
        assert r["success"], r
        assert r["count"] <= 3

    def test_invalid_limit_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_list_topics", {"limit": 0}))
        assert not r["success"]
        assert "limit" in r["error"]


class TestSearchTopicsMCP:
    """Handler-level tests for search_topics."""

    def test_search_finds_misspelling(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_search", {"query": "secrity"}))
        assert r["success"], r
        assert r["count"] > 0
        first = r["hits"][0]
        assert "slug" in first
        assert "score" in first
        assert isinstance(first["score"], float)

    def test_missing_query_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_search", {}))
        assert not r["success"]
        assert "query is required" in r["error"]

    def test_empty_query_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_search", {"query": ""}))
        assert not r["success"]


class TestSuggestTopicsMCP:
    """Handler-level tests for suggest_topics."""

    def test_suggest_returns_slugs(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_suggest", {"topic": "secur"}))
        assert r["success"], r
        assert isinstance(r["suggestions"], list)
        assert all(isinstance(s, str) for s in r["suggestions"])

    def test_missing_topic_rejected(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("lookup_suggest", {}))
        assert not r["success"]
        assert "topic is required" in r["error"]


# -- Dispatch safety -------------------------------------------------


class TestDispatchSafety:
    """The dispatch layer must never crash stdio."""

    def test_unknown_tool_returns_error(self) -> None:
        server = AttuneHelpMCPServer()
        r = asyncio.run(server.call_tool("nonexistent_tool", {}))
        assert not r["success"]
        assert "Unknown tool" in r["error"]

    def test_handler_exception_returns_error_not_raises(self) -> None:
        """Even if a handler raises, the server should return a dict."""
        from unittest.mock import AsyncMock

        server = AttuneHelpMCPServer()
        server._dispatch["lookup_topic"] = AsyncMock(
            side_effect=RuntimeError("simulated handler crash")
        )
        r = asyncio.run(server.call_tool("lookup_topic", {"topic": "x"}))
        assert not r["success"]
        assert "simulated handler crash" in r["error"]


# -- Path validation -------------------------------------------------


class TestPathValidation:
    """Defensive tests — path_validation should reject bad input."""

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValueError, match="null bytes"):
            validate_file_path("foo\x00.py")

    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            validate_file_path("")

    def test_etc_rejected(self) -> None:
        with pytest.raises(ValueError, match="system directory"):
            validate_file_path("/etc/passwd")

    def test_proc_rejected(self) -> None:
        with pytest.raises(ValueError, match="system directory"):
            validate_file_path("/proc/self/mem")

    def test_valid_relative_path_ok(self, tmp_path: Path) -> None:
        target = tmp_path / "ok.txt"
        target.write_text("hello")
        resolved = validate_file_path(str(target))
        assert resolved == target.resolve()

    def test_workspace_containment(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        with pytest.raises(ValueError, match="outside allowed"):
            validate_file_path(str(outside), allowed_dir=str(tmp_path))


# -- Handler construction --------------------------------------------


class TestHandlerConstruction:
    """AttuneHelpHandlers can be instantiated without a workspace."""

    def test_workspace_stored(self, tmp_path: Path) -> None:
        h = AttuneHelpHandlers(str(tmp_path))
        assert h._workspace_root == str(tmp_path)

    def test_engine_factory_without_override(self) -> None:
        h = AttuneHelpHandlers(".")
        engine = h._engine(template_dir=None)
        assert engine is not None
        # Falls through to bundled dir
        assert "templates" in str(engine.generated_dir)
