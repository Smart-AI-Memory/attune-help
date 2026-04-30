"""attune-help: Lightweight help runtime with progressive depth.

Provides template loading, progressive depth escalation,
audience adaptation, and feedback scoring — without the
full attune-ai authoring toolkit.
"""

from __future__ import annotations

from attune_help.demos import get_demo_path
from attune_help.engine import (
    AudienceProfile,
    HelpEngine,
    PopulatedTemplate,
    TemplateContext,
)
from attune_help.manifest import (
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
from attune_help.preamble import get_preamble  # noqa: F401
from attune_help.staleness import (
    DocStaleness,
    FeatureStaleness,
    StalenessReport,
    build_doc_footer,
    check_staleness,
    compute_semantic_hash,
    compute_source_hash,
    parse_doc_footer,
)
from attune_help.storage import LocalFileStorage, SessionStorage

__all__ = [
    # Engine
    "AudienceProfile",
    "HelpEngine",
    "LocalFileStorage",
    "PopulatedTemplate",
    "SessionStorage",
    "TemplateContext",
    "get_demo_path",
    "get_preamble",
    # Manifest
    "Feature",
    "FeatureManifest",
    "Manifest",
    "is_safe_feature_name",
    "load_manifest",
    "match_files_to_features",
    "resolve_topic",
    "save_manifest",
    "slugify",
    # Staleness
    "DocStaleness",
    "FeatureStaleness",
    "StalenessReport",
    "build_doc_footer",
    "check_staleness",
    "compute_semantic_hash",
    "compute_source_hash",
    "parse_doc_footer",
]

try:
    from importlib.metadata import version

    __version__ = version("attune-help")
except Exception:  # noqa: BLE001
    __version__ = "dev"
