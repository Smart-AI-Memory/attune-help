"""Tests for HelpEngine new APIs: simpler, reset, depth
terminal prompt."""

from __future__ import annotations

from pathlib import Path

import pytest

from attune_help import HelpEngine, LocalFileStorage
from attune_help.engine import _DEPTH_PROMPTS


def _engine(tmp_path: Path) -> HelpEngine:
    return HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))


def test_terminal_depth_prompt_not_silent() -> None:
    prompt = _DEPTH_PROMPTS[2]
    assert prompt != ""
    assert "simpler" in prompt
    assert "deepest" in prompt


def test_simpler_steps_down(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    eng.lookup("security-audit")
    eng.lookup("security-audit")
    eng.lookup("security-audit")
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 2

    out = eng.simpler("security-audit")
    assert out is not None
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 1


def test_simpler_clamps_at_zero(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    eng.lookup("security-audit")
    out = eng.simpler("security-audit")
    assert out is not None
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 0
    # Calling again stays at 0.
    eng.simpler("security-audit")
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 0


def test_reset_single_topic(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    eng.lookup("security-audit")
    eng.lookup("code-quality")
    eng.reset("security-audit")
    session = eng._storage.get_session("default")
    assert "security-audit" not in session["topics"]
    assert "code-quality" in session["topics"]


def test_reset_all(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    eng.lookup("security-audit")
    eng.lookup("code-quality")
    eng.reset()
    session = eng._storage.get_session("default")
    assert session["topics"] == {}
    assert session["order"] == []
    assert session["last_topic"] is None


def test_lookup_emits_depth_prompt(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    out = eng.lookup("security-audit")
    assert out is not None
    assert "tell me more" in out


def test_lookup_at_depth_two_emits_step_back_prompt(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    for _ in range(3):
        out = eng.lookup("security-audit")
    assert out is not None
    assert "simpler" in out


def test_get_summary_falls_back_to_bundled(tmp_path: Path) -> None:
    # Override dir with no summaries.json — must still
    # resolve bundled entries.
    (tmp_path / "cross_links.json").write_text("{}")
    eng = HelpEngine(
        template_dir=tmp_path,
        storage=LocalFileStorage(storage_dir=tmp_path / "sessions"),
    )
    from attune_help.engine import _load_summaries

    bundled = _load_summaries(eng._bundled_dir)
    if not bundled:
        pytest.skip("bundled summaries.json empty")
    any_key = next(iter(bundled))
    assert eng.get_summary(any_key) == bundled[any_key]


def test_precursor_warnings_multi_language(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    for path in ("foo.ts", "bar.rs", "baz.go", "qux.rb", "zap.java", "w.jsx"):
        result = eng.precursor_warnings(path, max_results=3)
        assert isinstance(result, list)
        assert len(result) <= 3
