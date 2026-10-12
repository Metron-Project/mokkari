"""Cache module.

This module provides the parts of response caching that don't depend on a backend:

- Cache: Protocol for a response cache passed to ``Session``
- TtlPolicy: How long a cache keeps each resource
- NO_CACHE: TTL for a resource that isn't cached at all
- RESOURCES: The resources Session caches under, from ``ResourceEndpoint``
- entry_tags, update_tags, create_tags: The tags Session stores entries with, and drops
  them by after a write, for a cache with ``invalidate_tags``
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
from urllib.parse import parse_qsl, urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

CacheKind = Literal["detail", "list"]
_KINDS: Final[frozenset[str]] = frozenset(get_args(CacheKind))


class ResourceEndpoint:
    """Constants for API resource endpoint names.

    These constants define the valid endpoint names used throughout the Session class
    for accessing different resource types in the Metron API. They're also the resources
    ``Session`` caches responses under.
    """

    ARC: Final[str] = "arc"
    CHARACTER: Final[str] = "character"
    COLLECTION: Final[str] = "collection"
    CREATOR: Final[str] = "creator"
    IMPRINT: Final[str] = "imprint"
    ISSUE: Final[str] = "issue"
    PUBLISHER: Final[str] = "publisher"
    READING_LIST: Final[str] = "reading_list"
    ROLE: Final[str] = "role"
    SERIES: Final[str] = "series"
    SERIES_TYPE: Final[str] = "series_type"
    TEAM: Final[str] = "team"
    UNIVERSE: Final[str] = "universe"
    PULL_LIST: Final[str] = "pull_list"
    WISH_LIST: Final[str] = "wish_list"


RESOURCES: Final[frozenset[str]] = frozenset(
    value for name, value in vars(ResourceEndpoint).items() if name.isupper()
)
"""The resources ``Session`` caches responses under, for use in a cache's ``ttl``."""


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

# A user's collection, pull list and wish list track what they own and want, so they change
# often, and serving a stale copy is more surprising than for shared reference data. They
# aren't cached unless the caller opts back in. Reading lists are per-user too, but are mostly
# public, curated lists that rarely change, so they're cached like reference data.
DEFAULT_TTLS: Final[Mapping[str, Ttl]] = MappingProxyType(
    {
        ResourceEndpoint.COLLECTION: NO_CACHE,
        ResourceEndpoint.PULL_LIST: NO_CACHE,
        ResourceEndpoint.WISH_LIST: NO_CACHE,
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
    calls it after each write that Metron didn't reject, including one that failed in a way
    that may still have applied it (e.g. a timeout or a 5xx). It's called with the resource
    written to, plus the few that read back the write directly: ``issue`` for a credit or
    variant write, and ``collection`` for acquiring a wish list item. Other cached data that
    embeds the written resource, such as a series' issue count or the creator names in an
    issue's credits, isn't invalidated and stays until it expires.

    A cache that also has an ``invalidate_tags(resource, tags)`` method gets a ``tags``
    keyword argument to ``store``: a frozenset of strings describing the entry, such as
    the ids of the objects in it and the fields its filters depend on. Updating (PATCH)
    or creating (POST) an object then calls ``invalidate_tags`` with the resource and the
    tags of the entries the write could have made stale, instead of ``invalidate``. It
    must remove every entry for ``resource`` stored with any of ``tags``. The other writes
    still call ``invalidate``.
    """

    def get(self, key: str) -> Any | None:
        """Return the unexpired value stored under ``key``, or ``None`` if there isn't one."""
        ...

    def store(self, key: str, value: Any, *, resource: str, kind: CacheKind) -> None:
        """Store ``value`` under ``key``, replacing any existing entry.

        ``key`` is the request URL with its query string. For per-user data (``collection``,
        ``pull_list``, ``reading_list`` and ``wish_list``) it also ends in ``#user=`` and a
        hash of the API token, so sessions with different tokens sharing a cache don't see
        each other's entries.

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


# Tags Session stores with each entry, for a cache with ``invalidate_tags``, so a write drops
# only the entries it could have made stale. They're computed here, from the URL Session
# requested and the response, so a backend only has to keep them and delete by them.
#
#   id:N             a detail entry for object N or one showing it, or a list holding it
#   field:F          a list whose filters depend on field F
#   exact:P=V        a list filtered on exact-match id P (e.g. cv_id) equal to V
#   exact:P          a list filtered on exact-match id P, whatever its value
#   any              dropped by every update: an entry Session can't describe more precisely
#   post             dropped by every create: a list with no exact-match id filter
TAG_ANY: Final[str] = "any"
TAG_CREATE: Final[str] = "post"

# Query parameters that don't filter.
_PAGINATION_PARAMS: Final[frozenset[str]] = frozenset({"page"})

# Filters matching a single value of an id field exactly, so a list filtered on one can only
# gain an object with that value. Each has the same name as the field it filters, and maps
# to how its value is normalized as Metron compares it: a number, or case-insensitive text.
_EXACT_PARAMS: Final[Mapping[str, Callable[[str], str]]] = MappingProxyType(
    {
        "cv_id": lambda value: str(int(value)),
        "gcd_id": lambda value: str(int(value)),
        "sku": str.lower,
        "upc": str.lower,
    }
)

# Each resource's list filters, from Metron's filtersets, mapped to the fields an update
# would have to change to move an object into or out of the list. A filter on data from
# another resource, such as a series' creators, maps to no fields: an update can't change it.
# Exact-match ids are listed in _EXACT_FILTERS instead. Any other parameter is unknown, and
# every update drops a list using one.
_NAME_FILTERS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {"name": ("name",), "modified_gt": ("modified",), "modified_lt": ("modified",)}
)
_COMIC_VINE_FILTERS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {**_NAME_FILTERS, "missing_cv_id": ("cv_id",), "missing_gcd_id": ("gcd_id",)}
)
_SERIES_OF_ISSUE: Final[tuple[str, ...]] = ("series",)
_FILTER_FIELDS: Final[Mapping[str, Mapping[str, tuple[str, ...]]]] = MappingProxyType(
    {
        ResourceEndpoint.ARC: _COMIC_VINE_FILTERS,
        ResourceEndpoint.CHARACTER: _COMIC_VINE_FILTERS,
        ResourceEndpoint.CREATOR: _COMIC_VINE_FILTERS,
        ResourceEndpoint.IMPRINT: _COMIC_VINE_FILTERS,
        ResourceEndpoint.ISSUE: {
            "modified_gt": ("modified",),
            "modified_lt": ("modified",),
            "missing_cv_id": ("cv_id",),
            "missing_gcd_id": ("gcd_id",),
            "cover_year": ("cover_date",),
            "cover_month": ("cover_date",),
            "cover_date_range_after": ("cover_date",),
            "cover_date_range_before": ("cover_date",),
            "store_date": ("store_date",),
            "store_date_range_after": ("store_date",),
            "store_date_range_before": ("store_date",),
            "foc_date": ("foc_date",),
            "foc_date_range_after": ("foc_date",),
            "foc_date_range_before": ("foc_date",),
            "number": ("number",),
            "alt_number": ("alt_number",),
            "rating": ("rating",),
            "upc_starts_with": ("upc",),
            "cover_hash": ("image",),
            "series_id": _SERIES_OF_ISSUE,
            "series_name": _SERIES_OF_ISSUE,
            "series_alt_names": _SERIES_OF_ISSUE,
            "series_q": _SERIES_OF_ISSUE,
            "series_volume": _SERIES_OF_ISSUE,
            "series_year_began": _SERIES_OF_ISSUE,
            "publisher_id": _SERIES_OF_ISSUE,
            "publisher_name": _SERIES_OF_ISSUE,
            "imprint_id": _SERIES_OF_ISSUE,
            "imprint_name": _SERIES_OF_ISSUE,
            "character_id": ("characters",),
            "team_id": ("teams",),
            "universe_id": ("universes",),
            # Credits aren't part of an issue update, and a credit write drops every issue.
            "creator_id": (),
            "role_id": (),
        },
        ResourceEndpoint.PUBLISHER: {
            **_COMIC_VINE_FILTERS,
            "alt_names": ("alt_names",),
            "q": ("name", "alt_names"),
        },
        ResourceEndpoint.ROLE: _NAME_FILTERS,
        ResourceEndpoint.SERIES: {
            **_COMIC_VINE_FILTERS,
            "alt_names": ("alt_names",),
            "q": ("name", "alt_names"),
            "publisher_id": ("publisher",),
            "publisher_name": ("publisher",),
            "imprint_id": ("imprint",),
            "imprint_name": ("imprint",),
            "series_type_id": ("series_type",),
            "series_type": ("series_type",),
            "status": ("status",),
            "language": ("language",),
            "volume": ("volume",),
            "year_began": ("year_began",),
            "year_end": ("year_end",),
            # These match a series by its issues, which a series update doesn't change.
            "creator_id": (),
            "character_id": (),
            "team_id": (),
            "universe_id": (),
            "role_id": (),
        },
        ResourceEndpoint.SERIES_TYPE: _NAME_FILTERS,
        ResourceEndpoint.TEAM: _COMIC_VINE_FILTERS,
        ResourceEndpoint.UNIVERSE: {**_NAME_FILTERS, "designation": ("designation",)},
    }
)
_COMIC_VINE_IDS: Final[frozenset[str]] = frozenset({"cv_id", "gcd_id"})
_EXACT_FILTERS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        ResourceEndpoint.ARC: _COMIC_VINE_IDS,
        ResourceEndpoint.CHARACTER: _COMIC_VINE_IDS,
        ResourceEndpoint.CREATOR: _COMIC_VINE_IDS,
        ResourceEndpoint.IMPRINT: _COMIC_VINE_IDS,
        ResourceEndpoint.ISSUE: _COMIC_VINE_IDS | {"sku", "upc"},
        ResourceEndpoint.PUBLISHER: _COMIC_VINE_IDS,
        ResourceEndpoint.SERIES: _COMIC_VINE_IDS,
        ResourceEndpoint.TEAM: _COMIC_VINE_IDS,
    }
)

# A resource's issue list (e.g. ``character/5/issue_list``) holds the issues whose field
# here includes the resource, so it's filtered on that field.
_ISSUE_LIST_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        ResourceEndpoint.ARC: "arcs",
        ResourceEndpoint.CHARACTER: "characters",
        ResourceEndpoint.SERIES: "series",
        ResourceEndpoint.TEAM: "teams",
    }
)

# Fields of a resource's detail that show other objects of the same resource (by id and
# name), so a write to one of those objects can change the detail. Metron keeps a series'
# associations on both series, so linking two changes both details.
_RELATED_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {ResourceEndpoint.ISSUE: "reprints", ResourceEndpoint.SERIES: "associated"}
)

# Every update changes an object's modification time.
_ALWAYS_UPDATED: Final[str] = "modified"


def _exact_value(param: str, value: object) -> str | None:
    """Return ``value`` of exact-match filter ``param`` as Metron compares it, or ``None``.

    ``None`` means the value can't be normalized (or is empty, which Metron ignores), so
    nothing can be concluded from it.
    """
    text = str(value).strip()
    if not text:
        return None
    try:
        return _EXACT_PARAMS[param](text)
    except ValueError:
        return None


def _api_path(url: str) -> list[str]:
    """Return the segments of ``url``'s path after the API's ``api`` prefix."""
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    return segments[1:] if segments[:1] == ["api"] else segments


def _id_tags(items: Any) -> set[str]:
    """Return the ``id:`` tags of ``items``, a list of objects or ids, or ``{TAG_ANY}``."""
    if not isinstance(items, list):
        return {TAG_ANY}
    return {
        f"id:{item['id']}"
        if isinstance(item, dict) and "id" in item
        else f"id:{item}"
        if isinstance(item, int)
        else TAG_ANY
        for item in items
    }


def _related_tags(resource: str, values: Mapping[str, Any]) -> set[str]:
    """Return the ``id:`` tags of the objects of ``resource`` that ``values`` relates to."""
    field = _RELATED_FIELDS.get(resource)
    if field is None or values.get(field) is None:
        return set()
    return _id_tags(values[field])


def entry_tags(key: str, value: Any, *, resource: str, kind: CacheKind) -> frozenset[str]:
    """Return the tags of the cache entry for ``key``.

    Args:
        key: The URL the entry was fetched from, with its query string.
        value: The response.
        resource: The resource it's cached under.
        kind: ``"detail"`` or ``"list"``.

    Returns:
        The tags describing what the entry holds; see ``Cache``.
    """
    unknown = frozenset({TAG_ANY, TAG_CREATE})
    path = _api_path(key)
    if kind == "detail":
        if (
            len(path) == 2  # noqa: PLR2004
            and path[0] == resource
            and isinstance(value, dict)
            and str(value.get("id")) == path[1]
        ):
            # A related object's name is shown, so a write to it drops this entry too.
            return frozenset({f"id:{path[1]}"} | _related_tags(resource, value))
        return unknown

    results = value.get("results") if isinstance(value, dict) else None
    if not isinstance(results, list):
        return unknown
    tags = _id_tags(results)
    if path != [resource]:
        if not (
            resource == ResourceEndpoint.ISSUE
            and len(path) == 3  # noqa: PLR2004
            and path[2] == "issue_list"
            and path[0] in _ISSUE_LIST_FIELDS
        ):
            return unknown
        tags.add(f"field:{_ISSUE_LIST_FIELDS[path[0]]}")
    return frozenset(tags | _filter_tags(resource, urlsplit(key).query))


def _filter_tags(resource: str, query: str) -> set[str]:
    """Return the tags of a list of ``resource`` filtered by the URL query string ``query``."""
    filter_fields = _FILTER_FIELDS.get(resource, {})
    exact_filters = _EXACT_FILTERS.get(resource, frozenset())
    tags = set()
    has_exact = False
    for param, value in parse_qsl(query, keep_blank_values=True):
        if param in _PAGINATION_PARAMS:
            continue
        if param in exact_filters and (normalized := _exact_value(param, value)) is not None:
            tags.update((f"exact:{param}={normalized}", f"exact:{param}"))
            has_exact = True
        elif param in filter_fields:
            tags.update(f"field:{field}" for field in filter_fields[param])
        else:
            tags.add(TAG_ANY)
    if not has_exact:
        tags.add(TAG_CREATE)
    return tags


def _exact_tags(resource: str, values: Mapping[str, Any]) -> set[str]:
    """Return the tags of lists that ``values``' exact-match ids could put an object in."""
    tags = set()
    for param in _EXACT_FILTERS.get(resource, frozenset()).intersection(values):
        if values[param] is None or values[param] == "":
            continue
        normalized = _exact_value(param, values[param])
        tags.add(f"exact:{param}" if normalized is None else f"exact:{param}={normalized}")
    return tags


def update_tags(resource: str, object_id: int, fields: Mapping[str, Any]) -> frozenset[str]:
    """Return the tags of entries that updating an object could make stale.

    Those are its detail entry, lists holding it, lists filtered on a field the update sets
    (or on its modification time, which every update changes), and lists filtered on an
    exact-match id equal to the new value. Lists filtered on any other value of that id
    can't gain the object, and any it leaves already hold it. Details of objects it's
    related to (see ``_RELATED_FIELDS``) show it, so they're dropped too: those it was
    related to through its ``id:`` tag, and those it's now related to through theirs.

    Args:
        resource: The resource updated.
        object_id: The id of the object updated.
        fields: The fields the update sent, with their new values.

    Returns:
        The tags to pass to ``invalidate_tags``.
    """
    tags = {TAG_ANY, f"id:{object_id}", f"field:{_ALWAYS_UPDATED}"}
    tags.update(f"field:{field}" for field in fields)
    tags.update(_exact_tags(resource, fields))
    tags.update(_related_tags(resource, fields))
    return frozenset(tags)


def create_tags(resource: str, created: Mapping[str, Any]) -> frozenset[str]:
    """Return the tags of entries that creating an object could make stale.

    Those are the lists a new object could join: every list but those filtered on an
    exact-match id the object doesn't have, and the details of objects it's related to (see
    ``_RELATED_FIELDS``), which may now show it.

    Args:
        resource: The resource created.
        created: The new object, as Metron returned it.

    Returns:
        The tags to pass to ``invalidate_tags``.
    """
    tags = {TAG_CREATE}
    tags.update(_exact_tags(resource, created))
    tags.update(_related_tags(resource, created))
    # Without the id in the response, lists filtered on any value of it might gain the object.
    tags.update(
        f"exact:{param}" for param in _EXACT_FILTERS.get(resource, frozenset()).difference(created)
    )
    return frozenset(tags)
