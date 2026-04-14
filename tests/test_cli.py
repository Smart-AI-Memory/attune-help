"""Smoke tests for the attune-help CLI."""

from __future__ import annotations

import pytest
from attune_help.cli import main


def test_version_flag_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """``--version`` prints the version and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "attune-help" in captured.out


def test_missing_command_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """Running with no subcommand prints usage and exits nonzero."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_lookup_missing_topic_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    """Looking up a nonexistent topic returns exit code 1."""
    exit_code = main(["lookup", "this-topic-definitely-does-not-exist-xyz"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "No help for" in captured.err


def test_list_runs(capsys: pytest.CaptureFixture[str]) -> None:
    """``list`` exits cleanly (0 or 1 depending on bundled content)."""
    exit_code = main(["list", "--limit", "3"])
    # Either topics exist (0) or not (1) — both are valid smoke outcomes.
    assert exit_code in (0, 1)


def test_search_empty_match_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    """Searching for something guaranteed absent returns exit code 1."""
    exit_code = main(["search", "zzz-nonexistent-query-xyz"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "No matches" in captured.err


def test_invalid_renderer_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """argparse rejects an unknown --renderer value."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--renderer", "bogus", "lookup", "anything"])
    assert exc_info.value.code != 0
