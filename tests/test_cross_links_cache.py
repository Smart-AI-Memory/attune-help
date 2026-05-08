"""mtime-aware caching of cross_links.json.

Verifies:

- First call hits disk and caches.
- Subsequent calls with unchanged mtime hit cache.
- Rewriting the file (mtime change) triggers a reload.
- Missing file returns empty without poisoning the cache.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from attune_help.templates import (
    _CROSS_LINKS_CACHE,
    _load_cross_links,
    invalidate_cross_links_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Ensure tests don't share cache state."""
    invalidate_cross_links_cache()
    yield
    invalidate_cross_links_cache()


def _bump_mtime(path: Path) -> None:
    """Force mtime forward by at least one nanosecond.

    macOS HFS+ stores 1s-resolution mtimes, so naive rewrites in the
    same second don't change ``st_mtime_ns``. This explicitly sets a
    later mtime so the cache invalidation path is exercised.
    """
    now_ns = path.stat().st_mtime_ns
    later = (now_ns + 1_000_000_000, now_ns + 1_000_000_000)
    os.utime(path, ns=later)


def test_first_call_loads_from_disk(tmp_path: Path) -> None:
    (tmp_path / "cross_links.json").write_text(json.dumps({"foo": ["bar"]}))
    result = _load_cross_links(tmp_path)
    assert result == {"foo": ["bar"]}


def test_second_call_with_unchanged_file_hits_cache(tmp_path: Path, monkeypatch) -> None:
    """When mtime hasn't changed, the second call must not re-read the file."""
    cl = tmp_path / "cross_links.json"
    cl.write_text(json.dumps({"foo": ["bar"]}))
    _load_cross_links(tmp_path)  # prime the cache

    read_calls = 0
    real_read = Path.read_text

    def counting_read(self, *args, **kwargs):
        nonlocal read_calls
        if self == cl:
            read_calls += 1
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read)
    _load_cross_links(tmp_path)
    _load_cross_links(tmp_path)
    assert read_calls == 0, "cache hit should not re-read the file"


def test_mtime_change_triggers_reload(tmp_path: Path) -> None:
    cl = tmp_path / "cross_links.json"
    cl.write_text(json.dumps({"v": 1}))
    first = _load_cross_links(tmp_path)
    assert first == {"v": 1}

    cl.write_text(json.dumps({"v": 2}))
    _bump_mtime(cl)
    second = _load_cross_links(tmp_path)
    assert second == {"v": 2}


def test_missing_file_returns_empty_without_caching(tmp_path: Path) -> None:
    """Missing file returns empty AND doesn't seed the cache; a later
    creation of the file is picked up on the next call.
    """
    assert _load_cross_links(tmp_path) == {}
    assert str(tmp_path) not in _CROSS_LINKS_CACHE

    # Now create the file — the next call must pick it up
    (tmp_path / "cross_links.json").write_text(json.dumps({"new": ["entry"]}))
    assert _load_cross_links(tmp_path) == {"new": ["entry"]}


def test_invalidate_clears_cache(tmp_path: Path) -> None:
    cl = tmp_path / "cross_links.json"
    cl.write_text(json.dumps({"x": 1}))
    _load_cross_links(tmp_path)
    assert str(tmp_path) in _CROSS_LINKS_CACHE
    invalidate_cross_links_cache()
    assert str(tmp_path) not in _CROSS_LINKS_CACHE


# ---------------------------------------------------------------------------
# Parsed-template (path, mtime) cache
# ---------------------------------------------------------------------------


def test_parsed_template_cached_by_mtime(tmp_path: Path, monkeypatch) -> None:
    """``_parse_template_file`` must reuse cached output when mtime is stable."""
    from attune_help import templates

    templates.invalidate_template_cache()

    f = tmp_path / "concept.md"
    f.write_text("---\ntype: concept\n---\n# Title\n\n## Section\n\nbody\n")

    parse_calls = 0
    real_load = None

    import frontmatter as fm

    real_load = fm.load

    def counting_load(*args, **kwargs):
        nonlocal parse_calls
        parse_calls += 1
        return real_load(*args, **kwargs)

    monkeypatch.setattr(fm, "load", counting_load)

    a = templates._parse_template_file(f)
    b = templates._parse_template_file(f)
    c = templates._parse_template_file(f)

    assert a == b == c
    assert parse_calls == 1, "second/third call should hit cache, not re-parse"


def test_parsed_template_reloads_after_mtime_change(tmp_path: Path) -> None:
    from attune_help import templates

    templates.invalidate_template_cache()
    f = tmp_path / "concept.md"
    f.write_text("---\ntype: concept\n---\n# v1\n")

    first = templates._parse_template_file(f)
    assert first["title"] == "v1"

    f.write_text("---\ntype: concept\n---\n# v2\n")
    _bump_mtime(f)

    second = templates._parse_template_file(f)
    assert second["title"] == "v2"


def test_invalidate_template_cache_clears_entries(tmp_path: Path) -> None:
    from attune_help import templates

    f = tmp_path / "x.md"
    f.write_text("---\ntype: concept\n---\n# A\n")
    templates._parse_template_file(f)
    assert any(str(f) == k[0] for k in templates._PARSED_TEMPLATE_CACHE)

    templates.invalidate_template_cache()
    assert templates._PARSED_TEMPLATE_CACHE == {}
