"""Tests for topic discovery, search, and suggest."""

from __future__ import annotations

from pathlib import Path

from attune_help import HelpEngine, LocalFileStorage
from attune_help.discovery import (
    build_index,
    invalidate_index_cache,
    list_topics,
    search,
    suggest,
)

BUNDLED = Path(__file__).resolve().parent.parent / "src" / "attune_help" / "templates"


def test_build_index_finds_known_types() -> None:
    invalidate_index_cache()
    idx = build_index(BUNDLED)
    for t in ("concepts", "tasks", "references", "warnings"):
        assert t in idx
        assert len(idx[t]) > 0


def test_list_topics_type_filter() -> None:
    invalidate_index_cache()
    concepts = list_topics(BUNDLED, type_filter="concepts")
    tasks = list_topics(BUNDLED, type_filter="tasks")
    assert len(concepts) > 0
    assert len(tasks) > 0
    assert set(concepts).isdisjoint({"nonexistent-slug"})


def test_list_topics_limit() -> None:
    invalidate_index_cache()
    result = list_topics(BUNDLED, limit=5)
    assert len(result) == 5


def test_search_finds_misspelling() -> None:
    invalidate_index_cache()
    hits = search(BUNDLED, "secrity-audit", limit=5)
    slugs = [s for s, _ in hits]
    assert any("security" in s for s in slugs)


def test_search_substring_ranks_higher() -> None:
    invalidate_index_cache()
    hits = search(BUNDLED, "security", limit=10)
    assert any("security" in s for s, _ in hits)


def test_suggest_returns_slugs_only() -> None:
    invalidate_index_cache()
    hits = suggest(BUNDLED, "secur", limit=3)
    assert isinstance(hits, list)
    assert all(isinstance(s, str) for s in hits)


def test_engine_list_topics() -> None:
    eng = HelpEngine()
    result = eng.list_topics(type_filter="concepts", limit=5)
    assert len(result) == 5


def test_engine_search() -> None:
    eng = HelpEngine()
    result = eng.search("security")
    assert result
    assert isinstance(result[0], tuple)
    assert isinstance(result[0][1], float)


def test_engine_lookup_miss_with_suggest(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    out = eng.lookup("nonexistent-slug-xyz", suggest_on_miss=True)
    assert out is not None
    assert "No help" in out


def test_engine_lookup_miss_with_suggest_fuzzy_hit(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    out = eng.lookup("secrity-audit", suggest_on_miss=True)
    assert out is not None
    assert "Did you mean" in out
    assert "security" in out


def test_engine_lookup_miss_without_flag_returns_none(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))
    out = eng.lookup("nonexistent-slug-xyz")
    assert out is None
