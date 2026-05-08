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
from attune_help.preamble import get_preamble  # noqa: F401
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
]

# Manifest, staleness, and freshness moved to attune-author. Importing
# them through ``attune_help.*`` still works via the deprecated shims
# in this package (they emit ``DeprecationWarning`` on first import).
# The shims are not eagerly imported here so that a plain
# ``import attune_help`` stays warning-free during the deprecation
# window.

try:
    from importlib.metadata import version

    __version__ = version("attune-help")
except Exception:  # noqa: BLE001
    __version__ = "dev"
