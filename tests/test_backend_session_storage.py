"""Tests for BackendSessionStorage — protocol parity with the file
backend, plus error-safety of the injected key/value backend.

No external service and no API: a dict-backed fake KVBackend drives
every case.
"""

from __future__ import annotations

import json

from attune_help.storage import BackendSessionStorage


class FakeKV:
    """In-memory KVBackend for tests (stash/retrieve over a dict)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def stash(self, key: str, value: str) -> bool:
        self.store[key] = value
        return True

    def retrieve(self, key: str) -> str | None:
        return self.store.get(key)


class BoomKV:
    """KVBackend whose every operation raises — exercises error-safety."""

    def stash(self, key: str, value: str) -> bool:
        raise RuntimeError("backend down")

    def retrieve(self, key: str) -> str | None:
        raise RuntimeError("backend down")


# ---------------------------------------------------------------------------
# Protocol parity with LocalFileStorage
# ---------------------------------------------------------------------------


def test_round_trip_new_schema() -> None:
    s = BackendSessionStorage(FakeKV())
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


def test_missing_key_returns_defaults() -> None:
    s = BackendSessionStorage(FakeKV())
    got = s.get_session("nobody")
    assert got["topics"] == {}
    assert got["order"] == []
    assert got["last_topic"] is None
    assert got["depth_level"] == 0


def test_legacy_payload_migrates_on_read() -> None:
    kv = FakeKV()
    kv.store["helpsess:alice"] = json.dumps(
        {"last_topic": "security", "depth_level": 1, "timestamp": 9_999_999_999}
    )
    got = BackendSessionStorage(kv).get_session("alice")
    assert got["topics"] == {"security": 1}
    assert got["order"] == ["security"]


def test_expired_session_returns_defaults() -> None:
    kv = FakeKV()
    kv.store["helpsess:alice"] = json.dumps(
        {
            "last_topic": "auth",
            "depth_level": 2,
            "topics": {"auth": 2},
            "order": ["auth"],
            "timestamp": 0,
        }
    )
    got = BackendSessionStorage(kv, ttl_seconds=1).get_session("alice")
    assert got["topics"] == {}
    assert got["last_topic"] is None


def test_malformed_payload_returns_defaults() -> None:
    kv = FakeKV()
    kv.store["helpsess:alice"] = "{not json"
    got = BackendSessionStorage(kv).get_session("alice")
    assert got["topics"] == {}
    assert got["last_topic"] is None


# ---------------------------------------------------------------------------
# Keying + configuration
# ---------------------------------------------------------------------------


def test_key_prefix_namespaces_writes() -> None:
    kv = FakeKV()
    BackendSessionStorage(kv, key_prefix="sess").set_session(
        "bob", {"last_topic": "x", "depth_level": 0, "topics": {"x": 0}, "order": ["x"]}
    )
    assert "sess:bob" in kv.store
    assert "helpsess:bob" not in kv.store


def test_distinct_users_are_isolated() -> None:
    s = BackendSessionStorage(FakeKV())
    s.set_session("a", {"last_topic": "ta", "depth_level": 1, "topics": {"ta": 1}, "order": ["ta"]})
    s.set_session("b", {"last_topic": "tb", "depth_level": 2, "topics": {"tb": 2}, "order": ["tb"]})
    assert s.get_session("a")["last_topic"] == "ta"
    assert s.get_session("b")["last_topic"] == "tb"


# ---------------------------------------------------------------------------
# Error-safety — backend failures never propagate into the runtime
# ---------------------------------------------------------------------------


def test_read_error_returns_defaults() -> None:
    got = BackendSessionStorage(BoomKV()).get_session("alice")
    assert got["topics"] == {}
    assert got["last_topic"] is None


def test_write_error_does_not_raise() -> None:
    # Must not propagate — mirrors LocalFileStorage's log-and-continue.
    BackendSessionStorage(BoomKV()).set_session(
        "alice", {"last_topic": "x", "depth_level": 0, "topics": {}, "order": []}
    )


def test_stash_returning_false_is_swallowed() -> None:
    class FalseKV:
        def stash(self, key: str, value: str) -> bool:
            return False

        def retrieve(self, key: str) -> str | None:
            return None

    # No exception; the write is simply best-effort.
    BackendSessionStorage(FalseKV()).set_session(
        "alice", {"last_topic": "x", "depth_level": 0, "topics": {}, "order": []}
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def test_exported_from_package_root() -> None:
    import attune_help

    assert hasattr(attune_help, "BackendSessionStorage")
    assert hasattr(attune_help, "KVBackend")
