"""Context-sensitive preamble extraction.

Reads the "Use X when..." one-liner from a feature's
task template. Works with any template directory — no
manifest or authoring toolkit required.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_preamble(
    feature_name: str,
    template_dir: str | Path,
) -> str | None:
    """Get the one-liner preamble for a feature.

    Reads the task template and returns the first
    non-empty paragraph after the h1 heading. Tries
    multiple on-disk layouts so the function works for
    both nested (`<feature>/task.md`) and flat
    (`tasks/use-<feature>.md`) template trees.

    Args:
        feature_name: Feature slug (e.g. "security-audit").
        template_dir: Path to templates directory. May
            be either the parent of nested feature dirs
            (demo layout) or the parent of `tasks/`
            (flat layout used by bundled templates).

    Returns:
        Preamble string, or None if not available.
    """
    if (
        not feature_name
        or "/" in feature_name
        or "\\" in feature_name
        or ".." in feature_name
        or "\x00" in feature_name
    ):
        return None

    base = Path(template_dir)
    candidates = [
        base / feature_name / "task.md",
        base / "tasks" / f"use-{feature_name}.md",
        base / "tasks" / f"{feature_name}.md",
        base / "tasks" / f"task-{feature_name}.md",
    ]

    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.debug("Cannot read %s: %s", path, e)
            continue
        preamble = _extract_preamble(text)
        if preamble:
            return preamble

    return None


def _extract_preamble(text: str) -> str | None:
    """Extract preamble from task template content.

    Skips YAML frontmatter and the h1 heading, returns
    the first non-empty paragraph.

    Args:
        text: Full task template content.

    Returns:
        Preamble line, or None.
    """
    lines = text.split("\n")

    # Skip frontmatter
    in_frontmatter = False
    content_start = 0
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            content_start = i + 1
            break

    # Find first non-empty, non-heading line
    for line in lines[content_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped

    return None
