"""Adapters that expose attune-help's bundled corpus to other packages.

The :mod:`attune_help.adapters.rag` module implements
:class:`attune_rag.corpus.help_adapter.HelpCorpusAdapter` so attune-rag
can build an :class:`attune_rag.corpus.attune_help.AttuneHelpCorpus`
without ever importing attune-help directly.
"""
