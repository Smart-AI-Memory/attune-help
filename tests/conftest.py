"""Shared fixtures for attune-help plugin tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"
PYPROJECT = REPO_ROOT / "pyproject.toml"


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
