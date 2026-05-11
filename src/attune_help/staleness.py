"""DEPRECATED: moved to :mod:`attune_author.staleness`.

Re-exported here for one minor release of attune-help so existing
imports keep working while consumers migrate. The shim emits
:class:`DeprecationWarning` on import.

Update your imports::

    from attune_author.staleness import check_staleness, StalenessReport

This shim will be removed in the next minor release of attune-help
(target: 2026-07-07 — see CHANGELOG).
"""

from __future__ import annotations

import warnings

try:
    from attune_author.staleness import (
        DocStaleness,
        FeatureStaleness,
        StalenessReport,
        build_doc_footer,
        check_staleness,
        compute_semantic_hash,
        compute_source_hash,
        parse_doc_footer,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attune_help.staleness is a deprecated shim that requires the "
        "'authoring' extra. Install with: pip install attune-help[authoring]. "
        "Or migrate your imports to attune_author.staleness directly."
    ) from exc

__all__ = [
    "DocStaleness",
    "FeatureStaleness",
    "StalenessReport",
    "build_doc_footer",
    "check_staleness",
    "compute_semantic_hash",
    "compute_source_hash",
    "parse_doc_footer",
]

warnings.warn(
    "attune_help.staleness is deprecated; import from attune_author.staleness. "
    "This shim will be removed in the next minor release of attune-help.",
    DeprecationWarning,
    stacklevel=2,
)
