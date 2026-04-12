"""Topic enumeration and fuzzy search.

Scans a template directory once and caches the result,
keyed on the directory path plus its mtime so the cache
self-invalidates when templates regenerate.
"""

from __future__ import annotations

import difflib
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_TYPE_DIRS = (
    "concepts",
    "tasks",
    "references",
    "quickstarts",
    "comparisons",
    "tips",
    "troubleshooting",
    "warnings",
    "errors",
    "faqs",
    "notes",
)

_INDEX_CACHE: dict[tuple[str, float], dict[str, list[str]]] = {}
_INDEX_LOCK = threading.Lock()


def invalidate_index_cache() -> None:
    """Clear the topic index cache."""
    with _INDEX_LOCK:
        _INDEX_CACHE.clear()


def build_index(generated_dir: Path) -> dict[str, list[str]]:
    """Return ``{type: [slug, ...]}`` for a template tree.

    Cached keyed on the directory path and its current
    mtime — touching the directory invalidates the cache
    automatically.

    Args:
        generated_dir: Path to the template directory.

    Returns:
        Dict mapping type name (``concepts``, ``tasks``,
        …) to a sorted list of slugs (filename stems).
    """
    gen = Path(generated_dir)
    try:
        mtime = gen.stat().st_mtime
    except OSError:
        return {}

    cache_key = (str(gen.resolve()), mtime)
    with _INDEX_LOCK:
        hit = _INDEX_CACHE.get(cache_key)
        if hit is not None:
            return hit

        index: dict[str, list[str]] = {}
        for type_name in _TYPE_DIRS:
            subdir = gen / type_name
            if not subdir.is_dir():
                continue
            slugs = sorted(p.stem for p in subdir.glob("*.md") if p.is_file())
            if slugs:
                index[type_name] = slugs

        _INDEX_CACHE[cache_key] = index
        return index


def list_topics(
    generated_dir: Path,
    type: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Enumerate topic slugs.

    Args:
        generated_dir: Template directory.
        type: Optional type filter (e.g. ``"concepts"``).
            ``None`` returns all types flattened.
        limit: Optional cap on returned items.

    Returns:
        Sorted list of slugs.
    """
    index = build_index(generated_dir)
    if type is not None:
        result = list(index.get(type, []))
    else:
        result = sorted({s for slugs in index.values() for s in slugs})
    if limit is not None:
        result = result[:limit]
    return result


def search(
    generated_dir: Path,
    query: str,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Fuzzy-search topic slugs.

    Uses ``difflib.SequenceMatcher`` against slug strings,
    plus a substring bonus so exact substrings outrank
    pure fuzzy matches.

    Args:
        generated_dir: Template directory.
        query: Search text.
        limit: Maximum results to return.

    Returns:
        List of ``(slug, score)`` tuples, best first.
        Scores range (0, 2]; 1.0 means perfect fuzzy
        match, values > 1 indicate substring hits.
    """
    if not query:
        return []

    query_l = query.lower().strip()
    slugs: set[str] = set()
    for bucket in build_index(generated_dir).values():
        slugs.update(bucket)

    scored: list[tuple[str, float]] = []
    for slug in slugs:
        ratio = difflib.SequenceMatcher(None, query_l, slug).ratio()
        if query_l in slug:
            ratio += 1.0
        if ratio >= 0.4:
            scored.append((slug, ratio))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:limit]


def suggest(
    generated_dir: Path,
    topic: str,
    limit: int = 5,
) -> list[str]:
    """Return fuzzy-match slugs for a missing topic.

    Thin wrapper around :func:`search` that drops scores.

    Args:
        generated_dir: Template directory.
        topic: The (likely misspelled) topic the caller
            looked up.
        limit: Maximum suggestions.

    Returns:
        List of slugs ranked by similarity.
    """
    return [slug for slug, _ in search(generated_dir, topic, limit=limit)]
