"""Storage protocol for session state.

Defines the SessionStorage interface and a default local
file implementation. Apps can swap in Redis, a database,
or any backend that implements get/set.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 4 * 3600  # 4 hours

# Default on-disk location for session files. Overridable via the
# ``ATTUNE_HELP_SESSIONS_DIR`` env var so tests/CI never touch the
# developer's real ``~/.attune-help/sessions/``.
_DEFAULT_SESSIONS_DIR = "~/.attune-help/sessions"


def _default_storage_dir() -> Path:
    """Resolve the default session directory (env-overridable)."""
    return Path(os.environ.get("ATTUNE_HELP_SESSIONS_DIR", _DEFAULT_SESSIONS_DIR)).expanduser()


class SessionStorage(Protocol):
    """Protocol for session state backends.

    Implement get_session() and set_session() to use a
    custom backend (Redis, database, etc.).
    """

    def get_session(self, user_id: str) -> dict[str, Any]:
        """Load session state for a user.

        Args:
            user_id: User identifier.

        Returns:
            Dict with last_topic and depth_level.
        """
        ...

    def set_session(self, user_id: str, state: dict[str, Any]) -> None:
        """Persist session state for a user.

        Args:
            user_id: User identifier.
            state: Session state dict to persist.
        """
        ...


class KVBackend(Protocol):
    """Minimal key/value backend for :class:`BackendSessionStorage`.

    Any object with these two methods works — an ``attune_redis``
    backend, attune's ``MemoryBackend``, or a hand-rolled dict wrapper.
    attune-help imports none of those; the integrator injects an
    instance, keeping the runtime dependency-free (tech.md ADR-002).

    ``stash`` returns ``True`` on a successful write, ``False`` (or
    raises) on failure. ``retrieve`` returns the stored string, or
    ``None`` when the key is absent.
    """

    def stash(self, key: str, value: str) -> bool:
        """Persist ``value`` under ``key``. Return True on success."""
        ...

    def retrieve(self, key: str) -> str | None:
        """Return the value for ``key``, or None if absent."""
        ...


def _defaults() -> dict[str, Any]:
    """Fresh session defaults."""
    return {
        "last_topic": None,
        "depth_level": 0,
        "topics": {},
        "order": [],
    }


def _migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """Translate an old session dict into the new schema.

    Old shape: ``{"last_topic": str, "depth_level": int}``.
    New shape adds ``topics`` (slug → depth) and ``order``
    (LRU list). Legacy sessions are mapped so the user's
    single-slot progress becomes the first entry in the
    per-topic dict.

    Args:
        data: Raw dict read from disk.

    Returns:
        Normalized dict with the new fields populated.
    """
    topics = data.get("topics")
    order = data.get("order")
    last_topic = data.get("last_topic")
    depth_level = data.get("depth_level", 0)

    if not isinstance(topics, dict):
        topics = {}
    if not isinstance(order, list):
        order = []

    if not topics and last_topic:
        topics = {last_topic: depth_level}
        order = [last_topic]

    return {
        "last_topic": last_topic,
        "depth_level": depth_level,
        "topics": topics,
        "order": order,
    }


def _serialize(state: dict[str, Any]) -> str:
    """Render a session dict as a timestamped JSON line.

    Shared by the file and backend storages so both persist the exact
    same schema (``last_topic``, ``depth_level``, ``topics``, ``order``,
    ``timestamp``).
    """
    payload = {
        "last_topic": state.get("last_topic"),
        "depth_level": state.get("depth_level", 0),
        "topics": state.get("topics", {}),
        "order": state.get("order", []),
        "timestamp": time.time(),
    }
    return json.dumps(payload) + "\n"


def _deserialize(raw: str | None, ttl_seconds: float) -> dict[str, Any]:
    """Parse a stored payload, applying TTL expiry and legacy migration.

    Returns fresh defaults when ``raw`` is missing, malformed, or older
    than ``ttl_seconds``. Shared by the file and backend storages.
    """
    if raw is None:
        return _defaults()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _defaults()
    if not isinstance(data, dict):
        return _defaults()
    ts = data.get("timestamp", 0)
    if time.time() - ts > ttl_seconds:
        return _defaults()
    return _migrate_legacy(data)


class LocalFileStorage:
    """File-based session storage (default implementation).

    Stores session state as JSON files in a configurable
    directory. Each user gets their own file. Supports
    4-hour TTL for session expiry.

    Args:
        storage_dir: Directory for session files.
            Defaults to ~/.attune-help/sessions/ (overridable via the
            ``ATTUNE_HELP_SESSIONS_DIR`` env var).
        ttl_seconds: Session time-to-live in seconds.
            Defaults to 4 hours.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        ttl_seconds: int = _SESSION_TTL_SECONDS,
    ) -> None:
        if storage_dir is None:
            self._dir = _default_storage_dir()
        else:
            self._dir = Path(storage_dir)
        self._ttl = ttl_seconds

    @staticmethod
    def _safe_filename(user_id: str) -> str:
        """Sanitize user_id into a safe filename.

        Allows only alphanumerics, hyphens, underscores,
        and dots. Prevents path traversal (CWE-22).

        Args:
            user_id: Raw user identifier.

        Returns:
            Sanitized filename string.

        Raises:
            ValueError: If user_id is empty or invalid.
        """
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", user_id)
        if not sanitized or sanitized in (".", ".."):
            raise ValueError(f"Invalid user_id: {user_id!r}")
        return sanitized

    def _resolve_path(self, user_id: str) -> Path:
        """Resolve and validate the session file path.

        Args:
            user_id: User identifier.

        Returns:
            Safe, resolved Path within the storage dir.
        """
        safe_name = self._safe_filename(user_id)
        path = self._dir / f"{safe_name}.json"
        # Containment check
        try:
            path.resolve().relative_to(self._dir.resolve())
        except ValueError as e:
            raise ValueError(f"Path traversal blocked: {user_id!r}") from e
        return path

    def get_session(self, user_id: str) -> dict[str, Any]:
        """Load session state from a JSON file.

        Legacy sessions (pre-0.4.0) are migrated on read
        so existing `.attune-help/sessions/` files work
        transparently after upgrade.

        Args:
            user_id: User identifier (used as filename).

        Returns:
            Session state dict, or fresh defaults if
            file is missing, corrupt, or expired.
        """
        defaults = _defaults()
        try:
            path = self._resolve_path(user_id)
        except ValueError:
            logger.warning("Invalid user_id: %s", user_id)
            return defaults
        try:
            if not path.exists():
                return defaults
            return _deserialize(path.read_text(encoding="utf-8"), self._ttl)
        except (json.JSONDecodeError, OSError, KeyError):
            return defaults

    def set_session(self, user_id: str, state: dict[str, Any]) -> None:
        """Write session state atomically.

        Args:
            user_id: User identifier.
            state: Session state dict to persist.
        """
        try:
            path = self._resolve_path(user_id)
        except ValueError:
            logger.warning("Invalid user_id: %s", user_id)
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(_serialize(state), encoding="utf-8")
            tmp.replace(path)  # replace() is cross-platform
        except OSError as e:
            logger.warning("Session write failed: %s", e)


class BackendSessionStorage:
    """Session storage backed by an injected key/value backend.

    A drop-in :class:`SessionStorage` that delegates persistence to any
    :class:`KVBackend` (an ``attune_redis`` backend, attune's
    ``MemoryBackend``, or a custom wrapper). Useful when session state
    must survive across hosts/processes rather than a single machine's
    ``~/.attune-help/sessions/`` directory.

    Schema, TTL, and legacy migration are identical to
    :class:`LocalFileStorage` — only the transport differs (a backend
    key instead of a file). attune-help imports no backend itself, so
    this adds no required dependency (tech.md ADR-002).

    Args:
        backend: The key/value backend to delegate to.
        key_prefix: Namespace prepended to every key. Defaults to
            ``"helpsess"``.
        ttl_seconds: Session time-to-live. Defaults to 4 hours, matching
            :class:`LocalFileStorage`.

    Example::

        from attune_help import BackendSessionStorage, HelpEngine
        storage = BackendSessionStorage(my_redis_backend)
        engine = HelpEngine(storage=storage)
    """

    def __init__(
        self,
        backend: KVBackend,
        *,
        key_prefix: str = "helpsess",
        ttl_seconds: int = _SESSION_TTL_SECONDS,
    ) -> None:
        self._backend = backend
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _key(self, user_id: str) -> str:
        """Backend key for a user's session."""
        return f"{self._prefix}:{user_id}"

    def get_session(self, user_id: str) -> dict[str, Any]:
        """Load session state from the backend.

        Returns fresh defaults on a miss, a malformed/expired payload, or
        any backend error — never raises into the runtime (matches
        :class:`LocalFileStorage`).

        Args:
            user_id: User identifier.

        Returns:
            Session state dict, or fresh defaults.
        """
        try:
            raw = self._backend.retrieve(self._key(user_id))
        except Exception as e:  # noqa: BLE001 - backend errors must not propagate
            logger.warning("Session backend read failed: %s", e)
            return _defaults()
        return _deserialize(raw, self._ttl)

    def set_session(self, user_id: str, state: dict[str, Any]) -> None:
        """Persist session state to the backend.

        Logs and no-ops on any backend failure (matches
        :class:`LocalFileStorage`); never raises into the runtime.

        Args:
            user_id: User identifier.
            state: Session state dict to persist.
        """
        try:
            self._backend.stash(self._key(user_id), _serialize(state))
        except Exception as e:  # noqa: BLE001 - backend errors must not propagate
            logger.warning("Session backend write failed: %s", e)
