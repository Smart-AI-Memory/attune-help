"""SessionStorage protocol verifier.

Reusable mixin that exercises the documented contract of
:class:`attune_help.storage.SessionStorage`. Any backend (LocalFileStorage,
Redis, database, in-memory) can plug into the mixin by implementing
``_make_storage()`` and inherit a uniform contract suite.

This guards the protocol surface so future backends (e.g. Redis) can be
verified against the same expectations rather than re-deriving them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


from attune_help.storage import LocalFileStorage, SessionStorage


class _InMemoryStorage:
    """Reference in-memory implementation of the SessionStorage protocol.

    Exists primarily to drive the protocol verifier — proves the mixin
    itself is implementation-agnostic.
    """

    def __init__(self) -> None:
        self._data: Dict[str, dict[str, Any]] = {}

    def get_session(self, user_id: str) -> dict[str, Any]:
        if user_id in self._data:
            return dict(self._data[user_id])
        return {
            "last_topic": None,
            "depth_level": 0,
            "topics": {},
            "order": [],
        }

    def set_session(self, user_id: str, state: dict[str, Any]) -> None:
        self._data[user_id] = dict(state)


class StorageProtocolTester(ABC):
    """Mixin that asserts SessionStorage protocol conformance.

    Subclass and implement ``_make_storage()`` to run the full contract
    suite against your backend.
    """

    @abstractmethod
    def _make_storage(self, tmp_path: Path) -> SessionStorage:
        """Return a fresh storage instance for one test."""

    def test_returns_defaults_for_unknown_user(self, tmp_path: Path) -> None:
        storage = self._make_storage(tmp_path)
        result = storage.get_session("nobody")
        assert result == {
            "last_topic": None,
            "depth_level": 0,
            "topics": {},
            "order": [],
        }

    def test_round_trip_preserves_topic_and_depth(self, tmp_path: Path) -> None:
        storage = self._make_storage(tmp_path)
        state = {
            "last_topic": "auth",
            "depth_level": 2,
            "topics": {"auth": 2},
            "order": ["auth"],
        }
        storage.set_session("alice", state)
        loaded = storage.get_session("alice")
        assert loaded["last_topic"] == "auth"
        assert loaded["depth_level"] == 2
        assert loaded["topics"] == {"auth": 2}
        assert loaded["order"] == ["auth"]

    def test_users_are_isolated(self, tmp_path: Path) -> None:
        storage = self._make_storage(tmp_path)
        storage.set_session(
            "alice",
            {"last_topic": "a", "depth_level": 1, "topics": {"a": 1}, "order": ["a"]},
        )
        storage.set_session(
            "bob",
            {"last_topic": "b", "depth_level": 3, "topics": {"b": 3}, "order": ["b"]},
        )
        assert storage.get_session("alice")["last_topic"] == "a"
        assert storage.get_session("bob")["last_topic"] == "b"

    def test_set_then_overwrite_replaces_state(self, tmp_path: Path) -> None:
        storage = self._make_storage(tmp_path)
        storage.set_session(
            "alice",
            {"last_topic": "a", "depth_level": 1, "topics": {"a": 1}, "order": ["a"]},
        )
        storage.set_session(
            "alice",
            {"last_topic": "b", "depth_level": 2, "topics": {"b": 2}, "order": ["b"]},
        )
        loaded = storage.get_session("alice")
        assert loaded["last_topic"] == "b"
        assert loaded["topics"] == {"b": 2}


class TestLocalFileStorageProtocol(StorageProtocolTester):
    """Run the protocol suite against LocalFileStorage."""

    def _make_storage(self, tmp_path: Path) -> SessionStorage:
        return LocalFileStorage(storage_dir=tmp_path / "sessions")


class TestInMemoryStorageProtocol(StorageProtocolTester):
    """Run the protocol suite against the reference in-memory backend."""

    def _make_storage(self, tmp_path: Path) -> SessionStorage:
        return _InMemoryStorage()
