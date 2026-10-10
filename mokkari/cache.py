"""Cache module.

This module provides the parts of response caching that don't depend on a backend:

- Cache: Protocol for a response cache passed to ``Session``
- NO_CACHE: TTL for a resource that isn't cached at all
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_TTLS",
    "NO_CACHE",
    "RESOURCES",
    "Cache",
    "CacheKind",
    "NoCache",
    "Ttl",
]

from datetime import timedelta
from enum import Enum
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    Protocol,
    get_args,
    runtime_checkable,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

CacheKind = Literal["detail", "list"]
_KINDS: Final[frozenset[str]] = frozenset(get_args(CacheKind))

RESOURCES: Final[frozenset[str]] = frozenset(
    {
        "arc",
        "character",
        "collection",
        "creator",
        "imprint",
        "issue",
        "publisher",
        "pull_list",
        "reading_list",
        "role",
        "series",
        "series_type",
        "team",
        "universe",
        "wish_list",
    }
)
"""The resources ``Session`` caches responses under, for use in ``SqliteCache``'s ``ttl``."""


class NoCache(Enum):
    """Type of ``NO_CACHE``, the TTL that keeps a resource out of the cache."""

    NO_CACHE = "NO_CACHE"

    def __repr__(self) -> str:
        """Return ``"NO_CACHE"``."""
        return "NO_CACHE"


NO_CACHE: Final = NoCache.NO_CACHE
"""TTL for a resource that isn't cached at all.

A distinct sentinel rather than ``timedelta(0)``: in Mokkari 4.x ``expire=0`` meant
"never expire", so a falsy value meaning "don't cache" would silently disable caching
for anyone porting that setting. A zero ``timedelta`` is rejected instead.
"""

Ttl = timedelta | NoCache | None
"""A lifetime, ``None`` to never expire, or ``NO_CACHE`` to not cache at all."""

# Per-user data changes whenever the user edits it on Metron, and serving a stale copy is more
# surprising than for shared reference data, so it isn't cached unless the caller opts back in.
DEFAULT_TTLS: Final[Mapping[str, Ttl]] = MappingProxyType(
    {
        "collection": NO_CACHE,
        "pull_list": NO_CACHE,
        "wish_list": NO_CACHE,
    }
)


@runtime_checkable
class Cache(Protocol):
    """Protocol for a response cache passed to ``Session``.

    Pass an object implementing this protocol as ``Session(cache=...)`` (or
    ``api(..., cache=...)``). ``SqliteCache`` is the bundled implementation.
    Implementations must be safe to call concurrently from multiple threads
    sharing one ``Session``.

    A cache may also have an ``invalidate(resource)`` method. If it does, ``Session``
    calls it after each successful write, with the resource written to and any others
    the write may have changed, so later reads don't return the pre-write copy.
    """

    def get(self, key: str) -> Any | None:
        """Return the unexpired value stored under ``key``, or ``None`` if there isn't one."""
        ...

    def store(self, key: str, value: Any, *, resource: str, kind: CacheKind) -> None:
        """Store ``value`` under ``key``, replacing any existing entry.

        ``resource`` is the first segment of the endpoint (e.g. ``"series"``), and
        ``kind`` is ``"detail"`` for a single object or ``"list"`` for a list
        endpoint, including every page of a paginated one. An implementation may
        use them to decide how long to keep the entry, or whether to keep it at all.
        """
        ...


def _check_ttl_key(name: str) -> None:
    """Raise ``ValueError`` unless ``name`` is a ``ttl`` key that ``ttl_for`` can match."""
    resource, sep, kind = name.partition(":")
    if sep and kind not in _KINDS:
        msg = f"TTL key {name!r} has an unknown kind {kind!r}: use one of {sorted(_KINDS)}"
        raise ValueError(msg)
    if resource == "*":
        if not sep:
            msg = "TTL key '*' needs a kind, e.g. '*:list'. Use default_ttl for everything else."
            raise ValueError(msg)
        return
    if resource not in RESOURCES:
        msg = (
            f"TTL key {name!r} has an unknown resource {resource!r}: use one of {sorted(RESOURCES)}"
        )
        raise ValueError(msg)


def _shorter(a: Ttl, b: Ttl) -> Ttl:
    """Return whichever of two TTLs keeps an entry for less time."""
    if a is NO_CACHE or b is NO_CACHE:
        return NO_CACHE
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
