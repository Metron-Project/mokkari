"""Cache coordination for ``Session``.

This private module provides:

- CacheCoordinator: Reads and stores responses in a ``Session``'s cache, and drops the
  entries a write may have made stale without letting an overlapping read store them again
- check_cache: Validates that an object can be used as a ``Session`` cache
"""

from __future__ import annotations

__all__ = ["CacheCoordinator", "check_cache"]

import inspect
import logging
import threading
from collections import Counter, defaultdict, deque
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

from mokkari import exceptions
from mokkari.cache import NO_CACHE, Cache, ResourceEndpoint, TtlPolicy, entry_tags

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from mokkari.cache import CacheKind

# Logged under Session's name, which is what callers filter cache messages by.
LOGGER = logging.getLogger("mokkari.session")

# Responses from these depend on whose token made the request (e.g. a private reading list),
# so their cache keys are scoped to the token and other tokens sharing the cache can't see them.
_PER_USER_RESOURCES: Final[frozenset[str]] = frozenset(
    {
        ResourceEndpoint.COLLECTION,
        ResourceEndpoint.PULL_LIST,
        ResourceEndpoint.READING_LIST,
        ResourceEndpoint.WISH_LIST,
    }
)

# How many of each resource's latest writes are remembered, for reads that finish during
# them (see ``CacheCoordinator._stale_tags``). A read that more writes overlapped treats
# every entry as stale.
WRITE_LOG_SIZE: Final[int] = 64


@runtime_checkable
class _TaggedCache(Cache, Protocol):
    """A ``Cache`` invalidated by tag, which ``store`` passes each entry's tags (see ``Cache``)."""

    def invalidate_tags(self, resource: str, tags: Collection[str]) -> object:
        """Remove every entry for ``resource`` stored with any of ``tags``."""
        ...


def check_cache(cache: object) -> None:
    """Raise ``CacheError`` unless ``cache`` can be called the way ``Session`` calls it.

    The ``Cache`` protocol check only sees that ``get`` and ``store`` exist, so this also
    checks they accept Session's arguments, catching e.g. a 4.x ``store(key, value)``.
    """
    if not isinstance(cache, Cache):
        msg = f"Cache must have get() and store() methods: {cache!r}"
        raise exceptions.CacheError(msg)
    store_kwargs: dict[str, Any] = {"resource": "series", "kind": "detail"}
    # A cache invalidated by tag is passed each entry's tags to store.
    if isinstance(cache, _TaggedCache):
        store_kwargs["tags"] = frozenset()
    for name, expected, args, kwargs in [
        ("get", "get(key)", ("key",), {}),
        ("store", f"store(key, value, *, {', '.join(store_kwargs)})", ("key", None), store_kwargs),
    ]:
        method = getattr(cache, name)
        try:
            signature = inspect.signature(method)
        except ValueError:
            # Some C-implemented callables can't be inspected; trust them.
            continue
        except TypeError as e:
            msg = f"Cache {name} must be a method: {cache!r}"
            raise exceptions.CacheError(msg) from e
        try:
            signature.bind(*args, **kwargs)
        except TypeError as e:
            msg = f"Cache must have a {expected} method, not {name}{signature}: {cache!r}"
            raise exceptions.CacheError(msg) from e


class CacheCoordinator:
    """Read, store and invalidate a ``Session``'s cached responses.

    A read takes ``invalidation_count`` for its resource before sending its request and
    passes it to ``store``, so a response fetched before a write invalidated entries like
    it isn't stored after the write, which would undo the invalidation. Reads of other
    resources, and reads whose entries the write didn't touch, are stored as usual.

    Every method is safe to call from multiple threads sharing one ``Session``. A cache
    that fails is logged rather than allowed to fail the request.
    """

    def __init__(self, cache: Cache | None, cache_user: str) -> None:
        """Initialize a CacheCoordinator.

        Args:
            cache: The response cache, or ``None`` if responses aren't cached.
            cache_user: Identifies the session's token in per-user cache keys.

        Raises:
            CacheError: If ``cache`` lacks a ``get`` or ``store`` method taking Session's
                arguments.
        """
        self.cache = cache
        self._cache_user = cache_user
        # Counts invalidations by resource, so a response fetched before one isn't stored
        # after it, while reads of other resources are stored as usual.
        self._lock = threading.Lock()
        self._invalidations: Counter[str] = Counter()
        # The tags each of a resource's latest invalidations dropped, or None if it dropped
        # every entry, so a read overlapping one is only discarded if it could be stale.
        self._invalidated_tags: defaultdict[str, deque[frozenset[str] | None]] = defaultdict(
            lambda: deque(maxlen=WRITE_LOG_SIZE)
        )

    @property
    def cache(self) -> Cache | None:
        """The response cache, or ``None`` if responses aren't cached."""
        return self._cache

    @cache.setter
    def cache(self, cache: Cache | None) -> None:
        # Checked here so a mis-wired cache fails now rather than on the first request.
        if cache is not None:
            check_cache(cache)
        self._cache = cache
        # Whether the cache is invalidated by tag is decided once, here, not on each use.
        self._tagged_cache = cache if isinstance(cache, _TaggedCache) else None

    def invalidation_count(self, resource: str) -> int:
        """Return how many times ``resource`` has been invalidated, to pass to ``store``."""
        return self._invalidations[resource]

    def _cache_key(self, key: str, resource: str) -> str:
        """Return ``key``, scoped to this session's token if ``resource`` is per-user data."""
        if resource in _PER_USER_RESOURCES:
            return f"{key}#user={self._cache_user}"
        return key

    def get(self, key: str, resource: str) -> Any | None:
        """Retrieve cached response data using the specified key.

        Args:
            key: The cache key to retrieve data for.
            resource: The resource the entry is cached under.

        Returns:
            Any | None: The cached response data if available and cache is configured,
                       None if not found, the cache isn't available, or reading it failed.
        """
        if self.cache is None:
            return None
        # A failing cache (e.g. its database is locked or unreadable) is treated as a miss,
        # so the data is fetched from Metron instead of the request failing. A database
        # shared between processes is expected to be locked now and then, so it's a warning,
        # with the traceback only when debugging.
        try:
            data = self.cache.get(self._cache_key(key, resource))
        except Exception as e:
            LOGGER.warning(
                "Cache get() failed; fetching from Metron: %r",
                e,
                exc_info=LOGGER.isEnabledFor(logging.DEBUG),
            )
            return None
        LOGGER.debug("Cache %s: %s", "miss" if data is None else "hit", key)
        return data

    def store(
        self, key: str, data: Any, resource: str, kind: CacheKind, *, invalidations: int
    ) -> None:
        """Store the provided data in the cache using the specified key.

        Args:
            key: The cache key to store the data under.
            data: The data to be stored in the cache.
            resource: The resource the entry is cached under.
            kind: ``"detail"`` or ``"list"``.
            invalidations: ``resource``'s ``invalidation_count`` from just before the
                request was sent.
        """
        if self.cache is None:
            return
        # A cache with a TTL policy (e.g. SqliteCache) wouldn't keep the data, so don't
        # describe it for one.
        ttl_policy = getattr(self.cache, "ttl_policy", None)
        if (
            isinstance(ttl_policy, TtlPolicy)
            and ttl_policy.ttl_for_value(data, resource=resource, kind=kind) is NO_CACHE
        ):
            return
        # Only a cache invalidated by tag takes tags (see Cache).
        tags = (
            None
            if self._tagged_cache is None
            else entry_tags(key, data, resource=resource, kind=kind)
        )
        # A write invalidated entries like this one while it was being fetched, so the data
        # may be from before it, and storing it would undo the invalidation.
        if self._stale_tags(resource, invalidations, tags) != frozenset():
            LOGGER.debug("Cache invalidated during the request; not caching %s", key)
            return
        # The data has already been fetched, so a cache that fails to store it (e.g. its
        # database is locked or the disk is full) is logged rather than failing the request.
        try:
            self.cache.store(
                self._cache_key(key, resource),
                data,
                resource=resource,
                kind=kind,
                **({} if tags is None else {"tags": tags}),
            )
        except Exception as e:
            # Logged like a failing get().
            LOGGER.warning(
                "Cache store() failed; not caching %s: %r",
                key,
                e,
                exc_info=LOGGER.isEnabledFor(logging.DEBUG),
            )
            return
        # The store isn't made under the lock, so one waiting on a locked database doesn't
        # hold up every other thread's store and invalidation. A write that invalidated
        # entries like this one meanwhile may have done so before it landed, so drop it again.
        stale = self._stale_tags(resource, invalidations, tags)
        if stale is None:
            LOGGER.debug("Cache invalidated during the store; dropping %s again", key)
            self._invalidate_resource(resource)
        elif stale:
            LOGGER.debug("Cache invalidated during the store; dropping %s again", key)
            self._invalidate_tags(resource, stale)

    def _stale_tags(
        self, resource: str, invalidations: int, tags: frozenset[str] | None
    ) -> frozenset[str] | None:
        """Return which of an entry's tags the invalidations made since a read dropped.

        Args:
            resource: The resource the entry is cached under.
            invalidations: ``resource``'s ``invalidation_count`` from just before the read
                was sent.
            tags: The entry's tags, or ``None`` if the cache isn't invalidated by tag.

        Returns:
            The tags to drop the entry by, which are empty if none of those invalidations
            could have made it stale, or ``None`` if one may have, but not by its tags.
        """
        with self._lock:
            missed = self._invalidations[resource] - invalidations
            if not missed:
                return frozenset()
            log = self._invalidated_tags[resource]
            if tags is None or missed > len(log):
                return None
            dropped = list(log)[-missed:]
        stale: set[str] = set()
        for dropped_tags in dropped:
            if dropped_tags is None:
                return None
            stale.update(tags & dropped_tags)
        return frozenset(stale)

    def invalidate(
        self, resources: Iterable[str], *, tags: Mapping[str, frozenset[str]] | None = None
    ) -> None:
        """Drop the cached entries of ``resources``, which a write may have made stale.

        Only a cache with an ``invalidate(resource)`` method, such as ``SqliteCache``, can
        be invalidated; other caches keep their entries until they expire. Either way, a
        read in flight is no longer stored, since it may be from before the write.

        Args:
            resources: The resources the write changed.
            tags: For some of ``resources``, the tags of the only entries to drop, if the
                cache has ``invalidate_tags``. Every entry of the rest is dropped.
        """
        with self._lock:
            for resource in resources:
                self._invalidations[resource] += 1
                if tags is not None and resource in tags:
                    self._invalidated_tags[resource].append(tags[resource])
                    self._invalidate_tags(resource, tags[resource])
                else:
                    self._invalidated_tags[resource].append(None)
                    self._invalidate_resource(resource)

    def _invalidate_tags(self, resource: str, tags: frozenset[str]) -> None:
        """Call the cache's ``invalidate_tags``, or ``invalidate`` if it hasn't got one.

        Like ``_invalidate_resource``, a failure is logged rather than raised.

        Args:
            resource: The resource whose cached entries to drop.
            tags: The tags of the entries to drop.
        """
        if self._tagged_cache is None:
            self._invalidate_resource(resource)
            return
        try:
            self._tagged_cache.invalidate_tags(resource, tags)
        except Exception:
            LOGGER.exception("Cache invalidate_tags(%r) failed; ignoring", resource)

    def _invalidate_resource(self, resource: str) -> None:
        """Call the cache's ``invalidate(resource)``, logging rather than raising a failure.

        After a write, which may already have been applied, raising would invite a retry
        that repeats it, or hide the write's own error. After a read, the data has already
        been fetched.

        Args:
            resource: The resource whose cached entries to drop.
        """
        invalidate = getattr(self.cache, "invalidate", None)
        if invalidate is None:
            return
        try:
            invalidate(resource)
        except Exception:
            LOGGER.exception("Cache invalidate(%r) failed; ignoring", resource)
