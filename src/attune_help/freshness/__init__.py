"""DEPRECATED: moved to :mod:`attune_author.freshness`.

Re-exported here for one minor release of attune-help so existing
imports keep working while consumers migrate. The shim emits
:class:`DeprecationWarning` on import.

Update your imports::

    from attune_author.freshness import SymbolExtractor, SymbolRecord

This shim will be removed in the next minor release of attune-help
(target: 2026-07-07 — see CHANGELOG).
"""

from __future__ import annotations

import warnings

try:
    from attune_author.freshness import SymbolExtractor, SymbolRecord
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attune_help.freshness is a deprecated shim that requires the "
        "'authoring' extra. Install with: pip install attune-help[authoring]. "
        "Or migrate your imports to attune_author.freshness directly."
    ) from exc

__all__ = ["SymbolExtractor", "SymbolRecord"]

warnings.warn(
    "attune_help.freshness is deprecated; import from attune_author.freshness. "
    "This shim will be removed in the next minor release of attune-help.",
    DeprecationWarning,
    stacklevel=2,
)
