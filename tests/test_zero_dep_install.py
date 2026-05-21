"""Verify attune-help honors its zero-required-deps contract (ADR-002).

Spins up a fresh venv with only ``python-frontmatter`` installed, installs
attune-help via ``--no-deps``, and asserts:

(a) ``import attune_help`` succeeds.
(b) ``import attune_help.manifest`` fails with a helpful ImportError
    that mentions the ``authoring`` extra.

This guards the architectural contract documented in ``tech.md``
ADR-002. Marked ``slow`` because it creates a real venv.

Uses ``uv venv`` + ``uv pip`` rather than stdlib ``venv``/``pip`` because
``ensurepip`` aborts on some Python builds (observed on cpython 3.11.14
macOS-aarch64).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_UV = shutil.which("uv")

_requires_uv = pytest.mark.skipif(
    _UV is None,
    reason="uv is required to build the isolated test venv (stdlib ensurepip is unreliable)",
)


def _make_venv(venv_dir: Path) -> Path:
    """Create a venv at ``venv_dir`` via ``uv venv`` and return its python."""
    subprocess.run(
        [_UV, "venv", "--quiet", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    return venv_dir / "bin" / "python"


def _install(py: Path, *args: str) -> None:
    subprocess.run(
        [_UV, "pip", "install", "--quiet", "--python", str(py), *args],
        check=True,
        capture_output=True,
    )


@pytest.mark.slow
@_requires_uv
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="venv layout differs on Windows; covered on Linux/macOS",
)
def test_attune_help_imports_without_authoring_extra(tmp_path: Path) -> None:
    py = _make_venv(tmp_path / "venv")
    _install(py, "python-frontmatter")
    _install(py, "--no-deps", "-e", str(REPO_ROOT))

    base = subprocess.run(
        [str(py), "-c", "import attune_help; print('ok')"],
        capture_output=True,
        text=True,
    )
    assert base.returncode == 0, f"base import failed without authoring extra: {base.stderr}"
    assert "ok" in base.stdout


@pytest.mark.slow
@_requires_uv
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="venv layout differs on Windows; covered on Linux/macOS",
)
@pytest.mark.parametrize(
    "shim_module",
    [
        "attune_help.manifest",
        "attune_help.staleness",
        "attune_help.freshness",
        "attune_help.freshness.symbols",
    ],
)
def test_shim_imports_fail_helpfully_without_authoring(tmp_path: Path, shim_module: str) -> None:
    py = _make_venv(tmp_path / "venv")
    _install(py, "python-frontmatter")
    _install(py, "--no-deps", "-e", str(REPO_ROOT))

    result = subprocess.run(
        [str(py), "-c", f"import {shim_module}"],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode != 0
    ), f"{shim_module} imported without [authoring]: it should have raised"
    assert "authoring" in result.stderr, (
        f"{shim_module} ImportError did not mention 'authoring' extra: " f"{result.stderr}"
    )
