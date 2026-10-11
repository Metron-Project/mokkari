"""Redis Cache module.

This module provides the following classes:

- RedisCache: A response cache kept in Redis, so several processes or hosts
  can share it

It requires a Redis client, installed with the ``redis`` extra
(``pip install mokkari[redis]``). The client is passed in rather than created
here, so this module never imports ``redis`` at runtime.
"""

from __future__ import annotations

__all__ = ["RedisCache"]

import json
import math
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, get_args

from mokkari.cache import NO_CACHE, CacheKind, TtlPolicy

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from redis import Redis

    from mokkari.cache import Ttl

# Bumped whenever the stored format changes, so an older and a newer Mokkari sharing one Redis
# use separate keys rather than reading each other's entries.
FORMAT_VERSION: Final[int] = 1

# How many keys clear() asks SCAN for, and clear() and invalidate() remove, at a time.
_BATCH_SIZE: Final[int] = 500

_KINDS: Final[tuple[CacheKind, ...]] = get_args(CacheKind)

# KEYS: entry, its record, its index set, then a set per tag
# ARGV: JSON value, TTL in ms ('' to never expire)
# Each index and tag set is a sorted set scored by each entry's expiry time in ms ('+inf' for
# never). Members whose entries have expired are dropped on every store, so a set holds only
# live entries, and it lives exactly as long as its longest-lived entry. An entry's record is
# the set of the sets it's in, expiring with it, so it can be taken out of them when it's
# stored again or removed, rather than left there once it never expires.
_STORE: Final[str] = """
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local sets = {}
for i = 3, #KEYS do
  sets[KEYS[i]] = true
end
for _, set in ipairs(redis.call('SMEMBERS', KEYS[2])) do
  if not sets[set] then
    redis.call('ZREM', set, KEYS[1])
  end
end
redis.call('DEL', KEYS[2])
redis.call('SADD', KEYS[2], unpack(KEYS, 3))
local score = '+inf'
if ARGV[2] == '' then
  redis.call('SET', KEYS[1], ARGV[1])
else
  redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
  redis.call('PEXPIRE', KEYS[2], ARGV[2])
  score = string.format('%.0f', now + tonumber(ARGV[2]))
end
for i = 3, #KEYS do
  redis.call('ZADD', KEYS[i], score, KEYS[1])
  redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', '(' .. string.format('%.0f', now))
  if redis.call('ZCOUNT', KEYS[i], '+inf', '+inf') > 0 then
    redis.call('PERSIST', KEYS[i])
  else
    -- The score comes back as a string Redis formats, which may not be a plain integer.
    local last = redis.call('ZRANGE', KEYS[i], -1, -1, 'WITHSCORES')
    redis.call('PEXPIREAT', KEYS[i], string.format('%.0f', tonumber(last[2])))
  end
end
return 0
"""

# ARGV: how many keys to unlink per call, the entry key prefix, then the record key prefix
# Removes entries and their records, taking each out of every set its record lists. Returns
# how many of the entries still existed.
_REMOVE_ENTRIES: Final[str] = """
local function remove_entries(entries)
  local batch = tonumber(ARGV[1])
  local records = {}
  for i, entry in ipairs(entries) do
    records[i] = ARGV[3] .. string.sub(entry, #ARGV[2] + 1)
    for _, set in ipairs(redis.call('SMEMBERS', records[i])) do
      redis.call('ZREM', set, entry)
    end
  end
  local removed = 0
  for i = 1, #entries, batch do
    local last = math.min(i + batch - 1, #entries)
    removed = removed + redis.call('UNLINK', unpack(entries, i, last))
    redis.call('UNLINK', unpack(records, i, last))
  end
  return removed
end
"""

# KEYS: index or tag sets
# ARGV: as for _REMOVE_ENTRIES
# Reads the sets, removes their entries and then the sets, all in one step, so nothing can be
# stored in between and a failure partway can't leave entries without an index.
_INVALIDATE: Final[str] = f"""{_REMOVE_ENTRIES}
local removed = remove_entries(redis.call('ZUNION', #KEYS, unpack(KEYS)))
redis.call('UNLINK', unpack(KEYS))
return removed
"""

# KEYS: entry
# ARGV: as for _REMOVE_ENTRIES
_DELETE: Final[str] = f"""{_REMOVE_ENTRIES}
return remove_entries({{KEYS[1]}})
"""


def _ttl_ms(ttl: timedelta) -> int:
    """Return ``ttl`` in whole milliseconds, rounded up so a positive TTL never becomes zero."""
    return max(1, math.ceil(ttl / timedelta(milliseconds=1)))


def _decode(key: bytes | str) -> str:
    """Return a key from Redis as a string, whichever way the client decodes responses."""
    return key.decode() if isinstance(key, bytes) else key


class RedisCache:
    """A response cache backed by Redis, with a configurable lifetime per resource.

    How long each entry is kept follows ``TtlPolicy``, exactly as for ``SqliteCache``:
    ``ttl`` sets a lifetime per resource and kind, ``default_ttl`` covers the rest, and
    empty lists are kept for at most ``empty_list_ttl``. ``RedisCache.NEVER`` and
    ``RedisCache.NO_CACHE`` are the same as ``None`` and ``NO_CACHE``.

    Entries expire through Redis's own TTLs, so there's nothing to clean up. Every key
    starts with ``key_prefix``, and ``clear()`` only removes those, so the Redis database
    can be shared with other data. Caches in any process that use the same Redis server
    and ``key_prefix`` share entries.

    Needs Redis 7.0 or later, and a single server rather than a Redis Cluster.
    ``invalidate`` and ``invalidate_tags`` find entries through per-resource index and tag
    sets, so if Redis is set to evict keys when it runs out of memory (``maxmemory-policy``
    other than ``noeviction``), an evicted set can leave its entries to be served until they
    expire. Give the cache enough memory that eviction doesn't happen, or use short TTLs.
    Each entry also has a record of the sets it's in, so storing it again or removing it
    takes it out of them, and a set left empty is deleted.

    Safe to share across threads, since redis-py clients are. Errors from the client,
    such as a ``redis.ConnectionError`` while Redis is down, are raised to the caller;
    ``Session`` logs a failing cache and carries on without it.

    Examples:
        >>> import redis
        >>> from datetime import timedelta
        >>> cache = RedisCache(
        ...     redis.Redis(host="localhost", port=6379),
        ...     default_ttl=timedelta(days=7),
        ...     ttl={"issue:list": timedelta(hours=6), "role": RedisCache.NEVER},
        ...     empty_list_ttl=timedelta(minutes=30),
        ... )
    """

    NEVER: Final = None
    NO_CACHE: Final = NO_CACHE

    def __init__(
        self,
        client: Redis,
        *,
        key_prefix: str = "mokkari:cache",
        default_ttl: Ttl = timedelta(days=7),
        ttl: Mapping[str, Ttl] | None = None,
        empty_list_ttl: Ttl = NO_CACHE,
    ) -> None:
        """Initialize a RedisCache.

        ``default_ttl``, ``ttl`` and ``empty_list_ttl`` build ``ttl_policy``; see
        ``TtlPolicy`` for what they accept.

        Args:
            client: A synchronous ``redis.Redis`` client. It's used as-is and never closed.
            key_prefix: Prefix for every key this cache creates.
            default_ttl: Lifetime for resources without an entry in ``ttl``.
            ttl: Lifetimes by resource and kind, merged over ``DEFAULT_TTLS``.
            empty_list_ttl: The longest a list response with no results is kept.

        Raises:
            TypeError: If ``TtlPolicy`` rejects a TTL or ``ttl`` key's type.
            ValueError: If ``TtlPolicy`` rejects a TTL or ``ttl`` key's value.
        """
        self.ttl_policy = TtlPolicy(default_ttl=default_ttl, ttl=ttl, empty_list_ttl=empty_list_ttl)
        self._client = client
        self._base = f"{key_prefix}:v{FORMAT_VERSION}:"
        self._index_base = f"{self._base}idx:"
        self._record_base = f"{self._index_base}entry:"
        self._store_script = client.register_script(_STORE)
        self._invalidate_script = client.register_script(_INVALIDATE)
        self._delete_script = client.register_script(_DELETE)

    def _key(self, key: str) -> str:
        return f"{self._base}{key}"

    def _record_key(self, key: str) -> str:
        """Return the key of the set of the index and tag sets the entry for ``key`` is in."""
        return f"{self._record_base}{key}"

    def _remove_args(self) -> list[int | str]:
        """Return the arguments the scripts removing entries take (see ``_REMOVE_ENTRIES``)."""
        return [_BATCH_SIZE, self._base, self._record_base]

    def _index_key(self, resource: str, kind: CacheKind) -> str:
        """Return the key of the sorted set holding the keys of ``resource``'s ``kind`` entries.

        Redis can't delete by resource, so ``invalidate`` reads the keys to delete from here.
        """
        return f"{self._index_base}{resource}:{kind}"

    def _tag_key(self, resource: str, tag: str) -> str:
        """Return the key of the sorted set holding the keys of ``resource``'s entries with ``tag``."""
        return f"{self._index_base}{resource}:tag:{tag}"

    def get(self, key: str) -> Any | None:
        """Retrieve unexpired data from the cache.

        Args:
            key: The cache key; see ``Cache.store``.

        Returns:
            The stored data, or ``None`` if it's missing or expired.
        """
        encoded = self._client.get(self._key(key))
        return None if encoded is None else json.loads(encoded)

    def store(
        self,
        key: str,
        value: Any,
        *,
        resource: str,
        kind: CacheKind,
        tags: Collection[str] = (),
    ) -> None:
        """Save data to the cache, replacing any existing entry for ``key``.

        Nothing is stored when the TTL for ``resource`` and ``kind`` is ``NO_CACHE``.
        A list response with no results is kept for no longer than ``empty_list_ttl``.

        Args:
            key: The cache key; see ``Cache.store``.
            value: JSON-serializable data to store.
            resource: The resource the entry holds, e.g. ``"series"``; see ``Cache.store``.
            kind: ``"detail"`` or ``"list"``.
            tags: Tags ``invalidate_tags`` can remove the entry by.
        """
        ttl = self.ttl_policy.ttl_for_value(value, resource=resource, kind=kind)
        if ttl is NO_CACHE:
            return
        self._store_script(
            keys=[
                self._key(key),
                self._record_key(key),
                self._index_key(resource, kind),
                *(self._tag_key(resource, tag) for tag in tags),
            ],
            args=[json.dumps(value), "" if ttl is None else _ttl_ms(ttl)],
        )

    def delete(self, key: str) -> bool:
        """Remove the entry for ``key``.

        For per-user data, ``key`` includes the ``#user=`` suffix ``Session`` adds (see
        ``Cache.store``), so the bare URL won't match. Use ``invalidate`` to drop every
        entry for such a resource instead.

        Returns:
            ``True`` if an entry was removed.
        """
        return self._delete_script(keys=[self._key(key)], args=self._remove_args()) > 0

    def invalidate(self, resource: str, kind: CacheKind | None = None) -> int:
        """Remove every entry for ``resource``, or only those of ``kind`` if given.

        ``Session`` calls this after each of its own writes, except updates and creates,
        which use ``invalidate_tags``. Call it yourself after changing data on Metron some
        other way, such as through the website.

        Returns:
            The number of entries removed.
        """
        indexes = [self._index_key(resource, k) for k in ((kind,) if kind else _KINDS)]
        return self._invalidate_script(keys=indexes, args=self._remove_args())

    def invalidate_tags(self, resource: str, tags: Collection[str]) -> int:
        """Remove every entry for ``resource`` stored with any of ``tags``.

        ``Session`` calls this instead of ``invalidate`` after updating or creating an
        object, with the tags of the entries the write could have made stale.

        Returns:
            The number of entries removed.
        """
        if not tags:
            return 0
        keys = [self._tag_key(resource, tag) for tag in tags]
        return self._invalidate_script(keys=keys, args=self._remove_args())

    def clear(self) -> int:
        """Remove every entry this cache's format version wrote under ``key_prefix``.

        Other keys are left alone, including entries an older or newer Mokkari wrote under
        the same ``key_prefix`` with a different stored format.

        Returns:
            The number of entries removed.
        """
        removed = 0
        batch: list[str] = []
        for key in self._client.scan_iter(match=f"{_glob_escape(self._base)}*", count=_BATCH_SIZE):
            batch.append(_decode(key))
            if len(batch) >= _BATCH_SIZE:
                removed += self._unlink_entries(batch)
                batch = []
        return removed + self._unlink_entries(batch)

    def _unlink_entries(self, keys: list[str]) -> int:
        """Remove ``keys``, returning how many of them were entries rather than index sets."""
        indexes = [key for key in keys if key.startswith(self._index_base)]
        entries = [key for key in keys if not key.startswith(self._index_base)]
        # Both are unlinked in one round trip, but separately, so only entries that still
        # existed are counted.
        pipe = self._client.pipeline(transaction=False)
        if indexes:
            pipe.unlink(*indexes)
        if entries:
            pipe.unlink(*entries)
        results = pipe.execute()
        return results[-1] if entries else 0


def _glob_escape(text: str) -> str:
    """Escape the characters ``SCAN MATCH`` treats as a glob pattern."""
    return re.sub(r"([*?\[\]\\])", r"\\\1", text)
