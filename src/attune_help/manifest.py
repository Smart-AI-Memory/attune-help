"""DEPRECATED: moved to :mod:`attune_author.manifest`.

Re-exported here for one minor release of attune-help so existing
imports keep working while consumers migrate. The shim emits
:class:`DeprecationWarning` on import.

Update your imports::

    from attune_author.manifest import Feature, FeatureManifest, load_manifest

This shim will be removed in the next minor release of attune-help
(target: 2026-07-07 — see CHANGELOG).
"""

from __future__ import annotations

import warnings

from attune_author.manifest import (
    Feature,
    FeatureManifest,
    Manifest,
    is_safe_feature_name,
    load_manifest,
    match_files_to_features,
    resolve_topic,
    save_manifest,
    slugify,
)

__all__ = [
    "Feature",
    "FeatureManifest",
    "Manifest",
    "is_safe_feature_name",
    "load_manifest",
    "match_files_to_features",
    "resolve_topic",
    "save_manifest",
    "slugify",
]

warnings.warn(
    "attune_help.manifest is deprecated; import from attune_author.manifest. "
    "This shim will be removed in the next minor release of attune-help.",
    DeprecationWarning,
    stacklevel=2,
)
