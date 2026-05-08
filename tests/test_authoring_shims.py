"""Verify the deprecated authoring re-export shims.

attune_help.manifest, attune_help.staleness, and
attune_help.freshness (+ .symbols) are kept as thin re-exports of the
relocated attune_author modules for one minor release. These tests
assert: (a) symbols still resolve through the old paths, and (b)
each shim emits :class:`DeprecationWarning` on import.
"""

from __future__ import annotations

import importlib
import sys
import warnings

import pytest

SHIMS = [
    "attune_help.manifest",
    "attune_help.staleness",
    "attune_help.freshness",
    "attune_help.freshness.symbols",
]


@pytest.mark.parametrize("module_name", SHIMS)
def test_shim_emits_deprecation_warning(module_name: str) -> None:
    sys.modules.pop(module_name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module(module_name)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations, f"{module_name} did not emit DeprecationWarning"
    assert any(
        module_name in str(w.message) for w in deprecations
    ), f"{module_name} DeprecationWarning did not name the module"


def test_manifest_symbols_resolve_through_shim() -> None:
    from attune_help.manifest import (
        Feature,
        FeatureManifest,
        is_safe_feature_name,
        load_manifest,
        save_manifest,
        slugify,
    )
    from attune_author.manifest import Feature as AuthorFeature

    assert Feature is AuthorFeature
    assert callable(is_safe_feature_name)
    assert callable(load_manifest)
    assert callable(save_manifest)
    assert callable(slugify)
    assert FeatureManifest.__module__.startswith("attune_author.")


def test_staleness_symbols_resolve_through_shim() -> None:
    from attune_help.staleness import (
        StalenessReport,
        check_staleness,
        compute_source_hash,
    )
    from attune_author.staleness import StalenessReport as AuthorReport

    assert StalenessReport is AuthorReport
    assert callable(check_staleness)
    assert callable(compute_source_hash)


def test_freshness_symbols_resolve_through_shim() -> None:
    from attune_help.freshness import SymbolExtractor, SymbolRecord
    from attune_help.freshness.symbols import SymbolExtractor as DeepExtractor
    from attune_author.freshness import SymbolExtractor as AuthorExtractor

    assert SymbolExtractor is AuthorExtractor
    assert DeepExtractor is AuthorExtractor
    assert SymbolRecord.__module__.startswith("attune_author.")
