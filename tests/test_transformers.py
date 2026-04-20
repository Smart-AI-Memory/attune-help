"""Tests for renderer transformers and HelpEngine
renderer selection."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from attune_help import HelpEngine, LocalFileStorage
from attune_help.engine import _RENDERERS
from attune_help.templates import PopulatedTemplate
from attune_help.transformers import (
    render_claude_code,
    render_json,
)


def _sample(type_: str = "concept") -> PopulatedTemplate:
    return PopulatedTemplate(
        template_id="con-demo",
        type=type_,
        subtype="",
        name="demo",
        title="Demo Topic",
        body="This is the body of a demo topic.",
        sections={"Overview": "Hello."},
        tags=["demo"],
        related=[],
        confidence="high",
        source="test",
        metadata={},
    )


# ----------------------------------------------------------------------
# render_json
# ----------------------------------------------------------------------


def test_render_json_round_trips() -> None:
    out = render_json(_sample())
    parsed = json.loads(out)
    assert parsed["template_id"] == "con-demo"
    assert parsed["title"] == "Demo Topic"
    assert parsed["tags"] == ["demo"]


def test_render_json_is_deterministic() -> None:
    out1 = render_json(_sample())
    out2 = render_json(_sample())
    assert out1 == out2


def test_render_json_registered_in_engine() -> None:
    assert "json" in _RENDERERS


# ----------------------------------------------------------------------
# render_claude_code: concept / task / unknown fallback
# ----------------------------------------------------------------------


def test_claude_code_emits_concept_body() -> None:
    out = render_claude_code(_sample("concept"))
    assert "Demo Topic" in out
    assert "This is the body" in out


def test_claude_code_emits_task_body() -> None:
    out = render_claude_code(_sample("task"))
    assert "This is the body" in out


def test_claude_code_unknown_type_falls_back_to_body() -> None:
    out = render_claude_code(_sample("whatever"))
    assert "This is the body" in out


# ----------------------------------------------------------------------
# set_renderer validation
# ----------------------------------------------------------------------


def test_set_renderer_rejects_unknown(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    with pytest.raises(ValueError) as excinfo:
        eng.set_renderer("bogus")
    assert "bogus" in str(excinfo.value)


def test_init_rejects_unknown_renderer(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        HelpEngine(
            storage=LocalFileStorage(storage_dir=tmp_path),
            renderer="bogus",
        )


def test_set_renderer_switches_live(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    eng.set_renderer("json")
    out = eng.lookup("security-audit")
    assert out is not None
    # Strip the depth prompt suffix so the JSON parses cleanly.
    assert out.startswith("{")
    payload = json.loads(out.split("\n\n*(")[0])
    assert "template_id" in payload


# ----------------------------------------------------------------------
# auto detection
# ----------------------------------------------------------------------


def test_auto_without_tty_falls_back_to_plain(tmp_path: Path) -> None:
    HelpEngine(
        storage=LocalFileStorage(storage_dir=tmp_path),
        renderer="auto",
    )
    with (
        patch.object(sys.stdout, "isatty", return_value=False),
        patch.dict("os.environ", {}, clear=False) as env,
    ):
        env.pop("CLAUDE_CODE", None)
        fn = HelpEngine._auto_detect_renderer()
    assert fn is _RENDERERS["plain"]


def test_auto_with_claude_code_env(tmp_path: Path) -> None:
    with patch.dict("os.environ", {"CLAUDE_CODE": "1"}, clear=False):
        fn = HelpEngine._auto_detect_renderer()
    assert fn is render_claude_code


# ----------------------------------------------------------------------
# render_claude_code: error / warning / tip branches
# ----------------------------------------------------------------------


def _sample_error() -> PopulatedTemplate:
    return PopulatedTemplate(
        template_id="err-demo",
        type="error",
        subtype="",
        name="demo-error",
        title="Demo Error",
        body="Error body.",
        sections={
            "Signature": "ValueError: bad input",
            "Root Cause": "The input was not validated.",
            "Resolution": "Add input validation.",
        },
        tags=["demo"],
        related=[],
        confidence="high",
        source="test",
        metadata={},
    )


def _sample_warning() -> PopulatedTemplate:
    return PopulatedTemplate(
        template_id="war-demo",
        type="warning",
        subtype="",
        name="demo-warning",
        title="Demo Warning",
        body="Warning body.",
        sections={
            "Condition": "When running on Windows",
            "Risk": "Path separators differ.",
            "Mitigation": "Use pathlib.Path.",
        },
        tags=["demo"],
        related=[],
        confidence="medium",
        source="test",
        metadata={},
    )


def _sample_tip() -> PopulatedTemplate:
    return PopulatedTemplate(
        template_id="tip-demo",
        type="tip",
        subtype="",
        name="demo-tip",
        title="Demo Tip",
        body="Tip body.",
        sections={
            "Recommendation": "Use caching.",
            "Why": "Reduces latency by 50%.",
        },
        tags=["demo"],
        related=[],
        confidence="high",
        source="test",
        metadata={},
    )


def test_claude_code_renders_error_sections() -> None:
    out = render_claude_code(_sample_error())
    assert "**Signature:**" in out
    assert "ValueError" in out
    assert "**Resolution:**" in out
    assert "Add input validation" in out


def test_claude_code_renders_warning_sections() -> None:
    out = render_claude_code(_sample_warning())
    assert "**When:**" in out
    assert "**Risk:**" in out
    assert "**Mitigation:**" in out


def test_claude_code_renders_tip_sections() -> None:
    out = render_claude_code(_sample_tip())
    assert "Use caching" in out
    assert "Reduces latency" in out


def test_claude_code_error_truncates_long_root_cause() -> None:
    t = _sample_error()
    t.sections["Root Cause"] = "A" * 300
    out = render_claude_code(t)
    assert "..." in out
    assert len([line for line in out.split("\n") if "A" * 200 in line]) == 0


# ----------------------------------------------------------------------
# render_marketplace
# ----------------------------------------------------------------------


def test_marketplace_has_yaml_frontmatter() -> None:
    from attune_help.transformers import render_marketplace

    out = render_marketplace(_sample())
    assert out.startswith("---")
    assert 'title: "Demo Topic"' in out
    assert "type: concept" in out


def test_marketplace_includes_related() -> None:
    from attune_help.transformers import render_marketplace

    t = _sample()
    t.related = [{"type": "Warning", "id": "war-demo"}]
    out = render_marketplace(t)
    assert "## See Also" in out
    assert "war-demo" in out


# ----------------------------------------------------------------------
# render_cli plain fallback
# ----------------------------------------------------------------------


def test_cli_plain_has_separator_and_sections() -> None:
    from attune_help.transformers import _render_cli_plain

    out = _render_cli_plain(_sample())
    assert "=" * 60 in out
    assert "Demo Topic" in out
    assert "[concept]" in out
    assert "Overview" in out
    assert "Tags: demo" in out


def test_cli_plain_includes_related() -> None:
    from attune_help.transformers import _render_cli_plain

    t = _sample()
    t.related = [{"type": "Tool Reference", "id": "ref-tool-demo"}]
    out = _render_cli_plain(t)
    assert "Related:" in out
    assert "ref-tool-demo" in out


# ----------------------------------------------------------------------
# engine.get() — #3
# ----------------------------------------------------------------------


def test_engine_get_returns_content(tmp_path: Path) -> None:
    """engine.get() should return rendered content without
    advancing session depth."""
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    # Use a known bundled template ID (con-tool-security-audit)
    out = eng.get("con-tool-security-audit")
    assert out is not None
    assert len(out) > 0


def test_engine_get_unknown_returns_none(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    assert eng.get("con-definitely-not-real-xyz") is None


def test_engine_get_does_not_advance_session(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    eng.get("con-tool-security-audit")
    eng.get("con-tool-security-audit")
    session = eng._storage.get_session("default")
    # get() doesn't track session state at all
    assert session["topics"] == {}
