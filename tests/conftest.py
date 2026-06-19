"""Shared fixtures for attune-help plugin tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Real home-dir state this layer's tests must never touch (they isolate to a
# tmp dir instead). The guard below is a regression alarm — see
# specs/test-isolation-guard/ and the workspace testing-conventions.md.
_GUARDED_PATHS = [Path.home() / ".attune-help" / "sessions"]


def _home_snapshot(p: Path):
    """Comparable snapshot: dir → child names; file → mtime; absent → None."""
    if p.is_dir():
        return frozenset(c.name for c in p.iterdir())
    if p.exists():
        return ("file", p.stat().st_mtime)
    return None


@pytest.fixture(scope="session", autouse=True)
def _guard_real_home_state():
    """Fail the run if any test wrote to real home-dir state (missing isolation)."""
    before = {p: _home_snapshot(p) for p in _GUARDED_PATHS}
    yield
    leaked = []
    for p in _GUARDED_PATHS:
        b, a = before[p], _home_snapshot(p)
        if isinstance(b, frozenset) or isinstance(a, frozenset):
            new = (a or frozenset()) - (b or frozenset())
            if new:
                leaked.append(f"{p}: new entries {sorted(new)[:5]}")
        elif b != a:
            leaked.append(f"{p}: created or modified")
    assert not leaked, (
        "Tests wrote to real home-dir state (missing isolation):\n  "
        + "\n  ".join(leaked)
        + "\nIsolate via the tmp-dir fixture — see testing-conventions.md."
    )


@pytest.fixture(autouse=True)
def _isolated_sessions_dir(tmp_path, monkeypatch):
    """Redirect LocalFileStorage's default session dir to a tmp path.

    Without this, tests that construct ``LocalFileStorage()`` with no
    ``storage_dir`` (e.g. test_mcp_server.py) read from / write to the
    developer's real ``~/.attune-help/sessions/``.
    """
    monkeypatch.setenv("ATTUNE_HELP_SESSIONS_DIR", str(tmp_path / "sessions"))


@pytest.fixture
def plugin_root() -> Path:
    """Absolute path to the plugin directory."""
    return PLUGIN_ROOT


@pytest.fixture
def pyproject_path() -> Path:
    """Absolute path to pyproject.toml."""
    return PYPROJECT
