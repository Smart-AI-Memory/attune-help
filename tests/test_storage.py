"""Tests for LocalFileStorage schema, TTL, and legacy
migration."""

from __future__ import annotations

import json
from pathlib import Path

from attune_help.storage import LocalFileStorage, _migrate_legacy


def test_round_trip_new_schema(tmp_path: Path) -> None:
    s = LocalFileStorage(storage_dir=tmp_path)
    s.set_session(
        "alice",
        {
            "last_topic": "auth",
            "depth_level": 2,
            "topics": {"auth": 2, "security": 1},
            "order": ["security", "auth"],
        },
    )
    got = s.get_session("alice")
    assert got["topics"] == {"auth": 2, "security": 1}
    assert got["order"] == ["security", "auth"]
    assert got["last_topic"] == "auth"
    assert got["depth_level"] == 2


def test_legacy_file_migrates_on_read(tmp_path: Path) -> None:
    raw = tmp_path / "alice.json"
    raw.write_text(
        json.dumps(
            {
                "last_topic": "security",
                "depth_level": 1,
                "timestamp": 9_999_999_999,
            }
        )
    )
    s = LocalFileStorage(storage_dir=tmp_path)
    got = s.get_session("alice")
    assert got["topics"] == {"security": 1}
    assert got["order"] == ["security"]
    assert got["last_topic"] == "security"
    assert got["depth_level"] == 1


def test_legacy_no_topic_yields_empty_maps(tmp_path: Path) -> None:
    raw = tmp_path / "alice.json"
    raw.write_text(
        json.dumps(
            {
                "last_topic": None,
                "depth_level": 0,
                "timestamp": 9_999_999_999,
            }
        )
    )
    s = LocalFileStorage(storage_dir=tmp_path)
    got = s.get_session("alice")
    assert got["topics"] == {}
    assert got["order"] == []


def test_expired_session_returns_defaults(tmp_path: Path) -> None:
    s = LocalFileStorage(storage_dir=tmp_path, ttl_seconds=1)
    raw = tmp_path / "alice.json"
    raw.write_text(
        json.dumps(
            {
                "last_topic": "auth",
                "depth_level": 2,
                "topics": {"auth": 2},
                "order": ["auth"],
                "timestamp": 0,
            }
        )
    )
    got = s.get_session("alice")
    assert got["topics"] == {}
    assert got["last_topic"] is None


def test_traversal_user_id_stays_contained(tmp_path: Path) -> None:
    s = LocalFileStorage(storage_dir=tmp_path)
    s.set_session(
        "../escape",
        {
            "last_topic": "x",
            "depth_level": 0,
            "topics": {"x": 0},
            "order": ["x"],
        },
    )
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    # Containment is enforced by resolve+relative_to, not
    # by stripping dots — what matters is the resolved
    # path stays inside the storage dir.
    resolved = written[0].resolve()
    resolved.relative_to(tmp_path.resolve())
    # And a round-trip still works via the sanitized name.
    got = s.get_session("../escape")
    assert got["topics"] == {"x": 0}


def test_migrate_legacy_is_idempotent() -> None:
    modern = {
        "last_topic": "a",
        "depth_level": 1,
        "topics": {"a": 1},
        "order": ["a"],
    }
    assert _migrate_legacy(modern) == modern
