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
    eng = HelpEngine(
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
