"""Tests for populate_progressive — per-topic history,
LRU eviction, and depth escalation."""

from __future__ import annotations

from pathlib import Path

from attune_help.progression import (
    _MAX_TOPICS,
    _record_topic,
    populate_progressive,
)
from attune_help.storage import LocalFileStorage

BUNDLED = Path(__file__).resolve().parent.parent / "src" / "attune_help" / "templates"


def test_record_topic_lru_eviction() -> None:
    session = {"last_topic": None, "depth_level": 0, "topics": {}, "order": []}
    for i in range(_MAX_TOPICS + 5):
        session = _record_topic(session, f"topic-{i}", 0)
    assert len(session["topics"]) == _MAX_TOPICS
    assert len(session["order"]) == _MAX_TOPICS
    assert "topic-0" not in session["topics"]
    assert f"topic-{_MAX_TOPICS + 4}" in session["topics"]


def test_record_topic_moves_existing_to_end() -> None:
    session = {"last_topic": None, "depth_level": 0, "topics": {}, "order": []}
    session = _record_topic(session, "a", 0)
    session = _record_topic(session, "b", 0)
    session = _record_topic(session, "a", 1)
    assert session["order"] == ["b", "a"]
    assert session["topics"] == {"a": 1, "b": 0}
    assert session["last_topic"] == "a"


def test_interleave_preserves_per_topic_depth(tmp_path: Path) -> None:
    storage = LocalFileStorage(storage_dir=tmp_path)

    r1 = populate_progressive(
        "security-audit",
        storage=storage,
        user_id="alice",
        generated_dir=BUNDLED,
    )
    assert r1 is not None
    assert r1.metadata["depth_level"] == 0

    r2 = populate_progressive(
        "code-quality",
        storage=storage,
        user_id="alice",
        generated_dir=BUNDLED,
    )
    assert r2 is not None
    assert r2.metadata["depth_level"] == 0

    r3 = populate_progressive(
        "security-audit",
        storage=storage,
        user_id="alice",
        generated_dir=BUNDLED,
    )
    assert r3 is not None
    assert (
        r3.metadata["depth_level"] == 1
    ), "interleaving a second topic should not reset security-audit"


def test_depth_caps_at_two(tmp_path: Path) -> None:
    storage = LocalFileStorage(storage_dir=tmp_path)
    for _ in range(5):
        r = populate_progressive(
            "security-audit",
            storage=storage,
            user_id="alice",
            generated_dir=BUNDLED,
        )
    assert r is not None
    assert r.metadata["depth_level"] == 2


def test_starting_level_override(tmp_path: Path) -> None:
    storage = LocalFileStorage(storage_dir=tmp_path)
    r = populate_progressive(
        "security-audit",
        storage=storage,
        user_id="alice",
        generated_dir=BUNDLED,
        starting_level=2,
    )
    assert r is not None
    assert r.metadata["depth_level"] == 2
