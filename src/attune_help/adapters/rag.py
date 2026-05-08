"""Adapter exposing attune-help's bundled corpus to attune-rag.

attune-rag declares a small structural ``HelpCorpusAdapter`` protocol
(``templates_root: Path``, ``version: str``). This module ships an
implementation so attune-rag's corpus factory can build the
``AttuneHelpCorpus`` without dynamically importing attune-help. The
direction of the dependency edge inverts: attune-rag knows nothing of
attune-help; attune-help imports rag's protocol and conforms to it.

Usage::

    from attune_help.adapters.rag import AttuneHelpAdapter
    from attune_rag.corpus.attune_help import AttuneHelpCorpus

    corpus = AttuneHelpCorpus(adapter=AttuneHelpAdapter())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from attune_help import __version__ as _help_version

_BUNDLED_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class AttuneHelpAdapter:
    """attune-help's default :class:`HelpCorpusAdapter` implementation.

    By default points at the bundled templates directory and reports
    the installed package version. Both fields are overridable so
    tests and downstream callers can supply their own corpus root or
    version string without subclassing.
    """

    templates_root: Path = field(default=_BUNDLED_TEMPLATES)
    version: str = field(default=_help_version)
