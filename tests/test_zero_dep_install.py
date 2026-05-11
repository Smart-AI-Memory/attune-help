"""Verify attune-help honors its zero-required-deps contract (ADR-002).

Spins up a fresh venv with only ``python-frontmatter`` installed, installs
attune-help via ``--no-deps``, and asserts:

(a) ``import attune_help`` succeeds.
(b) ``import attune_help.manifest`` fails with a helpful ImportError
    that mentions the ``authoring`` extra.

This guards the architectural contract documented in ``tech.md``
ADR-002. Marked ``slow`` because it creates a real venv.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="venv layout differs on Windows; covered on Linux/macOS",
)
def test_attune_help_imports_without_authoring_extra(tmp_path: Path) -> None:
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    py = venv_dir / "bin" / "python"
    pip = venv_dir / "bin" / "pip"

    subprocess.run(
        [str(pip), "install", "--quiet", "python-frontmatter"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(pip), "install", "--quiet", "--no-deps", "-e", str(REPO_ROOT)],
        check=True,
        capture_output=True,
    )

    base = subprocess.run(
        [str(py), "-c", "import attune_help; print('ok')"],
        capture_output=True,
        text=True,
    )
    assert base.returncode == 0, f"base import failed without authoring extra: {base.stderr}"
    assert "ok" in base.stdout


@pytest.mark.slow
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
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    py = venv_dir / "bin" / "python"
    pip = venv_dir / "bin" / "pip"

    subprocess.run(
        [str(pip), "install", "--quiet", "python-frontmatter"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(pip), "install", "--quiet", "--no-deps", "-e", str(REPO_ROOT)],
        check=True,
        capture_output=True,
    )

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
