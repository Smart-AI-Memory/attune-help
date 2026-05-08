"""DEPRECATED: moved to :mod:`attune_author.freshness.symbols`.

Re-exported here for one minor release of attune-help so existing
imports keep working while consumers migrate. The shim emits
:class:`DeprecationWarning` on import.

Update your imports::

    from attune_author.freshness.symbols import SymbolExtractor, SymbolRecord

This shim will be removed in the next minor release of attune-help
(target: 2026-07-07 — see CHANGELOG).
"""

from __future__ import annotations

import warnings

from attune_author.freshness.symbols import SymbolExtractor, SymbolRecord

__all__ = ["SymbolExtractor", "SymbolRecord"]

warnings.warn(
    "attune_help.freshness.symbols is deprecated; import from "
    "attune_author.freshness.symbols. This shim will be removed in the "
    "next minor release of attune-help.",
    DeprecationWarning,
    stacklevel=2,
)
