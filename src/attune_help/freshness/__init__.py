"""Symbol extraction for semantic-freshness staleness detection (Phase 1).

Known limitation — re-export shims:
    Pure re-export modules (``from pkg import *`` with no definitions) produce
    zero symbols. If a feature's ``files:`` list includes only shim files,
    ``compute_semantic_hash`` will return SHA-256("") for that feature.
    Mitigation: list the upstream implementation file alongside the shim in
    ``features.yaml``, or use Option B (per-symbol frontmatter) in a future
    release. Tracked for Phase 2 evaluation.
"""

from attune_help.freshness.symbols import SymbolExtractor, SymbolRecord

__all__ = ["SymbolExtractor", "SymbolRecord"]
