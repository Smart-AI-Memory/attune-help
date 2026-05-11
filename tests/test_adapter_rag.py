"""Tests for attune_help.adapters.rag — the attune-rag corpus adapter."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import attune_help
from attune_help.adapters.rag import AttuneHelpAdapter


def test_default_templates_root_points_to_bundled_dir() -> None:
    adapter = AttuneHelpAdapter()
    assert (
        adapter.templates_root.is_dir()
    ), f"bundled templates dir missing: {adapter.templates_root}"
    # Must live inside the installed package, not somewhere arbitrary.
    package_root = Path(attune_help.__file__).resolve().parent
    assert package_root in adapter.templates_root.resolve().parents


def test_default_version_matches_package_version() -> None:
    adapter = AttuneHelpAdapter()
    assert adapter.version == attune_help.__version__


def test_custom_root_and_version_override_defaults(tmp_path: Path) -> None:
    custom_root = tmp_path / "custom-corpus"
    custom_root.mkdir()
    adapter = AttuneHelpAdapter(
        templates_root=custom_root,
        version="9.9.9-test",
    )
    assert adapter.templates_root == custom_root
    assert adapter.version == "9.9.9-test"


def test_adapter_is_frozen() -> None:
    adapter = AttuneHelpAdapter()
    with pytest.raises(FrozenInstanceError):
        adapter.version = "0.0.0"  # type: ignore[misc]


def test_adapter_satisfies_help_corpus_adapter_protocol() -> None:
    """Structural conformance to attune-rag's HelpCorpusAdapter protocol.

    The protocol requires ``templates_root: Path`` and ``version: str``.
    We assert the shape directly instead of importing the protocol so
    this test runs even when attune-rag isn't installed.
    """
    adapter = AttuneHelpAdapter()
    assert isinstance(adapter.templates_root, Path)
    assert isinstance(adapter.version, str)
    assert adapter.version  # non-empty


def test_two_adapters_with_same_inputs_are_equal(tmp_path: Path) -> None:
    a = AttuneHelpAdapter(templates_root=tmp_path, version="1.0")
    b = AttuneHelpAdapter(templates_root=tmp_path, version="1.0")
    assert a == b
    # frozen dataclass instances are hashable.
    assert hash(a) == hash(b)
