"""Regression tests for preamble extraction across
both flat and nested template layouts, plus the edge
cases and security guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from attune_help import HelpEngine
from attune_help.preamble import _extract_preamble, get_preamble


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------------
# Flat layout (bundled templates use this)
# ----------------------------------------------------------------------


def test_flat_layout_use_prefix(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "use-security-audit.md",
        "---\ntype: task\n---\n\n"
        "# How to Run a Security Audit\n\n"
        "## Quick start\n\n"
        "Scan a directory for security issues.\n",
    )
    assert get_preamble("security-audit", tmp_path) == "Scan a directory for security issues."


def test_flat_layout_bare(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "git-workflow.md",
        "# Git Workflow\n\nBranch, commit, and push safely.\n",
    )
    assert get_preamble("git-workflow", tmp_path) == "Branch, commit, and push safely."


def test_flat_layout_task_prefix(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "task-debugging-sessions.md",
        "# Debugging Sessions\n\n" "Capture and replay a session to diagnose issues.\n",
    )
    assert (
        get_preamble("debugging-sessions", tmp_path)
        == "Capture and replay a session to diagnose issues."
    )


# ----------------------------------------------------------------------
# Nested layout (demos use this)
# ----------------------------------------------------------------------


def test_nested_layout(tmp_path: Path) -> None:
    _write(
        tmp_path / "security-audit" / "task.md",
        "---\nfeature: security-audit\n---\n\n"
        "# How to Run a Security Audit\n\n"
        "Point the scanner at a directory.\n",
    )
    assert get_preamble("security-audit", tmp_path) == "Point the scanner at a directory."


def test_nested_layout_wins_over_flat(tmp_path: Path) -> None:
    _write(
        tmp_path / "demo" / "task.md",
        "# Demo\n\nNested wins.\n",
    )
    _write(
        tmp_path / "tasks" / "use-demo.md",
        "# Demo\n\nFlat should not win.\n",
    )
    assert get_preamble("demo", tmp_path) == "Nested wins."


# ----------------------------------------------------------------------
# Priority ordering inside the flat layout
# ----------------------------------------------------------------------


def test_flat_use_prefix_wins_over_bare(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "use-foo.md",
        "# Foo\n\nFirst match.\n",
    )
    _write(
        tmp_path / "tasks" / "foo.md",
        "# Foo\n\nSecond match.\n",
    )
    assert get_preamble("foo", tmp_path) == "First match."


# ----------------------------------------------------------------------
# Missing / empty / invalid
# ----------------------------------------------------------------------


def test_missing_feature_returns_none(tmp_path: Path) -> None:
    assert get_preamble("not-here", tmp_path) is None


def test_empty_file_returns_none(tmp_path: Path) -> None:
    _write(tmp_path / "tasks" / "empty.md", "")
    assert get_preamble("empty", tmp_path) is None


def test_frontmatter_only_returns_none(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "only-fm.md",
        "---\ntype: task\n---\n",
    )
    assert get_preamble("only-fm", tmp_path) is None


def test_headings_only_returns_none(tmp_path: Path) -> None:
    _write(
        tmp_path / "tasks" / "just-headings.md",
        "# H1\n\n## H2\n\n### H3\n",
    )
    assert get_preamble("just-headings", tmp_path) is None


# ----------------------------------------------------------------------
# Security guards
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["", "../escape", "a/b", "a\\b", "null\x00byte"],
)
def test_rejects_traversal(tmp_path: Path, bad: str) -> None:
    assert get_preamble(bad, tmp_path) is None


# ----------------------------------------------------------------------
# _extract_preamble unit checks
# ----------------------------------------------------------------------


def test_extract_skips_frontmatter_and_heading() -> None:
    text = "---\n" "type: task\n" "---\n" "\n" "# Title\n" "\n" "First real line.\n"
    assert _extract_preamble(text) == "First real line."


def test_extract_handles_no_frontmatter() -> None:
    text = "# Title\n\nHello.\n"
    assert _extract_preamble(text) == "Hello."


# ----------------------------------------------------------------------
# End-to-end against bundled templates
# ----------------------------------------------------------------------


def test_bundled_templates_resolve_skill_feature() -> None:
    engine = HelpEngine()
    result = engine.preamble("security-audit")
    assert result is not None
    assert len(result) > 0
