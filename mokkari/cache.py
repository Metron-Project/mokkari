"""Cache module.

This module provides the parts of response caching that don't depend on a backend:

- Cache: Protocol for a response cache passed to ``Session``
- TtlPolicy: How long a cache keeps each resource
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
    "TtlPolicy",
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

        ``resource`` is the type of object the endpoint returns, normally its first
        segment (e.g. ``"series"``), but ``"issue"`` for a resource's issue list such as
        ``series/5/issue_list``. ``kind`` is ``"detail"`` for a single object or ``"list"``
        for a list endpoint, including every page of a paginated one. An implementation may
        use them to decide how long to keep the entry, or whether to keep it at all.
        """
        ...


def _check_ttl_key(name: object) -> None:
    """Raise unless ``name`` is a ``ttl`` key that ``ttl_for`` can match.

    Raises:
        TypeError: If ``name`` isn't a string.
        ValueError: If ``name`` has an unknown resource or kind.
    """
    if not isinstance(name, str):
        msg = f"TTL key must be a string, not {name!r}"
        raise TypeError(msg)
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


class TtlPolicy:
    """How long a cache keeps the entries for each resource, shared by every cache backend.

    How long an entry lives is looked up by ``"{resource}:{kind}"``, then by
    ``"{resource}"``, then by ``"*:{kind}"`` (e.g. ``"*:list"`` for every list
    endpoint), then falls back to ``default_ttl``. A TTL is a positive
    ``timedelta``, ``None`` for an entry that never expires, or ``NO_CACHE`` for
    one that isn't cached at all. ``collection``, ``pull_list`` and ``wish_list``
    default to ``NO_CACHE`` (see ``DEFAULT_TTLS``); add them to ``ttl`` to cache
    them anyway.

    A list response with no results is kept for at most ``empty_list_ttl``, so a
    search that found nothing doesn't outlive the data arriving on Metron. By
    default empty lists aren't cached at all.
    """

    def __init__(
        self,
        *,
        default_ttl: Ttl = timedelta(days=7),
        ttl: Mapping[str, Ttl] | None = None,
        empty_list_ttl: Ttl = NO_CACHE,
    ) -> None:
        """Check and store the TTLs.

        Args:
            default_ttl: Lifetime for resources without an entry in ``ttl``.
                ``None`` never expires them, and ``NO_CACHE`` caches nothing by default.
            ttl: Lifetimes keyed by ``"{resource}:{kind}"``, ``"{resource}"`` or
                ``"*:{kind}"``, merged over ``DEFAULT_TTLS``. ``resource`` is one of
                ``RESOURCES`` and ``kind`` is ``"detail"`` or ``"list"``.
            empty_list_ttl: The longest a list response with no results is kept.
                It only ever shortens the usual TTL: ``NO_CACHE`` doesn't cache
                empty lists, and ``None`` gives them the usual TTL.

        Raises:
            TypeError: If any TTL isn't a ``timedelta``, ``None`` or ``NO_CACHE``, or a
                ``ttl`` key isn't a string.
            ValueError: If any TTL is zero or negative, or a ``ttl`` key names an unknown
                resource or kind.
        """
        for name in ttl or {}:
            _check_ttl_key(name)
        self._ttl = {**DEFAULT_TTLS, **(ttl or {})}
        self._default_ttl = default_ttl
        self._empty_list_ttl = empty_list_ttl
        for name, value in [
            ("default_ttl", default_ttl),
            ("empty_list_ttl", empty_list_ttl),
            *self._ttl.items(),
        ]:
            if value is None or value is NO_CACHE:
                continue
            if not isinstance(value, timedelta):
                msg = f"TTL for {name!r} must be a timedelta, None or NO_CACHE, not {value!r}"
                raise TypeError(msg)
            if value <= timedelta(0):
                msg = (
                    f"TTL for {name!r} must be positive: {value}. "
                    "Use NO_CACHE to keep it out of the cache, or None to never expire it."
                )
                raise ValueError(msg)

    def ttl_for(self, resource: str, kind: CacheKind) -> Ttl:
        """Return how long an entry for ``resource`` and ``kind`` is kept.

        Returns:
            The lifetime, ``None`` if it never expires, or ``NO_CACHE`` if it isn't cached.
        """
        for name in (f"{resource}:{kind}", resource, f"*:{kind}"):
            if name in self._ttl:
                return self._ttl[name]
        return self._default_ttl

    def ttl_for_value(self, value: Any, *, resource: str, kind: CacheKind) -> Ttl:
        """Return how long ``value``, a response for ``resource`` and ``kind``, is kept.

        This is ``ttl_for``, shortened to ``empty_list_ttl`` for a list with no results.

        Returns:
            The lifetime, ``None`` if it never expires, or ``NO_CACHE`` if it isn't cached.
        """
        ttl = self.ttl_for(resource, kind)
        if kind == "list" and isinstance(value, dict) and value.get("count") == 0:
            ttl = _shorter(ttl, self._empty_list_ttl)
        return ttl
