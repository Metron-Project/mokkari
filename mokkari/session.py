"""Session module.

This module provides the following classes:

- Session: Main API client for interacting with the Metron Comics Database
"""

__all__ = ["Session"]

# The HEADER_* constants imported from mokkari.rate_limit below lived here until the
# rate-limit header handling moved there, so they stay importable from here through 5.x.
# New code should import them from mokkari.rate_limit.

import functools
import hashlib
import http.cookiejar
import json
import logging
import platform
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import format_datetime as format_http_datetime
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, TypeAlias
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, TypeAdapter, ValidationError
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from mokkari._cache_coordinator import CacheCoordinator
from mokkari._endpoints import (
    CatalogEndpoints,
    CollectionEndpoints,
    PullListEndpoints,
    ReadingListEndpoints,
    WishListEndpoints,
)
from mokkari._version import __version__
from mokkari.cache import Cache, CacheKind, ResourceEndpoint, create_tags, update_tags
from mokkari.exceptions import ApiError, AuthenticationError, RateLimiterError, RateLimitError
from mokkari.rate_limit import (
    DEFAULT_BURST_PERIOD,
    HEADER_BURST_LIMIT,  # noqa: F401 (re-exported, see the note under __all__)
    HEADER_BURST_REMAINING,  # noqa: F401 (re-exported, see the note under __all__)
    HEADER_BURST_RESET,  # noqa: F401 (re-exported, see the note under __all__)
    HEADER_SUSTAINED_LIMIT,  # noqa: F401 (re-exported, see the note under __all__)
    HEADER_SUSTAINED_REMAINING,  # noqa: F401 (re-exported, see the note under __all__)
    HEADER_SUSTAINED_RESET,  # noqa: F401 (re-exported, see the note under __all__)
    RateLimiter,
    RateLimitStatus,
)
from mokkari.schemas.issue import (
    BaseIssue,
)
from mokkari.utils import format_time

if TYPE_CHECKING:
    from mokkari._endpoints._helpers import EndpointHelpers

LOGGER = logging.getLogger(__name__)

# Constants
REQUEST_TIMEOUT: Final[int] = 20
# Metron always sends ``Retry-After`` with a 429, so a rejection without one is
# unexpected. Pagination retries a page this many times in a row before giving up.
MAX_UNTIMED_RATE_LIMIT_RETRIES: Final[int] = 3
# Pagination gives up on a page after this many 429s in a row, whether or not they carry
# ``Retry-After``, so a call can't hang forever behind another client saturating the account.
# With a ``rate_limiter`` it also stops one that returns from ``acquire`` without blocking
# (the ``RateLimiter`` protocol allows it) from turning the retry into a tight loop. It's
# generous because each retry is normally a real, timed wait.
MAX_RATE_LIMIT_RETRIES: Final[int] = 20
# Connections kept open per host. ``requests`` defaults to 10, but a ``Session`` may be shared
# across many threads; past the pool size urllib3 discards the extra connections (and logs
# a warning each time) instead of reusing them, so every request beyond it pays a new handshake.
HTTP_POOL_MAXSIZE: Final[int] = 32
METRON_URL = "https://metron.cloud/api/{}/"
LOCAL_URL = "http://127.0.0.1:8000/api/{}/"

# Reports whether the most recent response was served from Metron's cache
# ("HIT") or generated fresh ("MISS").
HEADER_CACHE: Final[str] = "X-Cache"


class _BearerAuth(AuthBase):
    """Attach the API token as a Bearer ``Authorization`` header.

    Passing this as ``auth`` rather than setting the header directly matters: when a
    request has no ``auth``, ``requests`` applies any ``~/.netrc`` entry for the host,
    which would replace the Bearer header with Basic credentials.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self._token}"
        return r


class _ServerRateLimitError(RateLimitError):
    """A ``RateLimitError`` for a 429 that Metron returned.

    Unlike one raised locally before a request is sent, retrying this one after the
    rate limiter has backed off can succeed.
    """


# Given a write's response (``None`` if it raised), returns the tags of the entries of the
# written resource to drop, or ``None`` to drop them all.
_WriteTags = Callable[[requests.Response | None], frozenset[str] | None]


def _created_tags(resource: str) -> _WriteTags:
    """Return a ``_WriteTags`` for creating a ``resource``, which reads the new object back."""

    def tags(response: requests.Response | None) -> frozenset[str] | None:
        if response is None or not response.ok:
            return None
        try:
            created = response.json()
        except ValueError:
            return None
        if not isinstance(created, dict) or "id" not in created:
            return None
        return create_tags(resource, created)

    return tags


_JSON_CONTENT_TYPE: Final[str] = "application/json;charset=utf-8"

# A write's request body: one model, or a list of them for a bulk endpoint (e.g. credits).
# ``list`` is invariant, so its items are ``Any`` to accept e.g. ``list[CreditPost]``.
_Payload: TypeAlias = BaseModel | list[Any]


def _http_date(moment: datetime) -> str:
    """Format ``moment`` as an HTTP date (RFC 9110), taking a naive datetime as UTC."""
    moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    return format_http_datetime(moment, usegmt=True)


@functools.cache
def _type_adapter(tp: Any) -> TypeAdapter[Any]:
    """Return a ``TypeAdapter`` for ``tp``, built once rather than on every validation."""
    return TypeAdapter(tp)


def _multipart_payload(
    fields: dict[str, Any],
) -> tuple[dict[str, tuple[str, bytes]] | None, dict[str, Any]]:
    """Split a model's fields into multipart/form-data file uploads and form fields.

    The ``image`` field, a path, becomes the file upload if the file exists. ``None`` values
    are dropped, since form data can't represent them, and nested dicts are JSON-encoded.
    Lists are sent as repeated form fields by ``requests``.

    Args:
        fields: The model's dumped fields, including ``image``. It's modified.

    Returns:
        The file uploads (``None`` if there's no image to send), and the form fields.
    """
    files = None
    if img := fields.pop("image"):
        img_path = Path(img)
        if img_path.exists():
            files = {"image": (img_path.name, img_path.read_bytes())}
            LOGGER.debug("Image File: %s", img)
        else:
            LOGGER.warning("Image file not found: %s", img)
    form = {
        k: json.dumps(v, default=str) if isinstance(v, dict) else v
        for k, v in fields.items()
        if v is not None
    }
    return files, form


class _SessionCore:
    """The transport, rate limiting, caching and validation every endpoint shares.

    ``Session`` combines this with the endpoint mixins in ``mokkari._endpoints``. Use
    ``Session`` rather than this class.
    """

    def __init__(
        self,
        api_token: str,
        *,
        cache: Cache | None = None,
        user_agent: str | None = None,
        dev_mode: bool = False,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Initialize a Session object with authentication and configuration.

        Sets up the session with proper authentication headers, API endpoint URL,
        and optional caching. The user agent is automatically constructed to include
        the library version and system information.

        Args:
            api_token: API token for Bearer-token authentication.
            cache: Optional response cache, such as a ``SqliteCache``.
            user_agent: Optional custom user agent string to prepend to the default.
            dev_mode: If True, use local development server instead of production.
            rate_limiter: Optional pacing gate dispatched on every HTTP send,
                in place of the default fail-fast check. Defaults to ``None``.

        Raises:
            AuthenticationError: If the api_token is missing or empty.
            CacheError: If ``cache`` lacks a ``get`` or ``store`` method taking Session's arguments.
        """
        # Guards against a token read from an unset environment variable, which the
        # type hint alone won't catch at runtime.
        if not api_token:
            raise AuthenticationError

        self.api_token = api_token
        self.header = {
            "User-Agent": f"{f'{user_agent} ' if user_agent is not None else ''}"
            f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        # Kept out of ``header`` so the token isn't logged with the request headers.
        self._auth = _BearerAuth(api_token)
        self.api_url = LOCAL_URL if dev_mode else METRON_URL
        # Per-user cache keys identify the token by a hash rather than storing the token.
        self._cache_coordinator = CacheCoordinator(
            cache, cache_user=hashlib.sha256(api_token.encode()).hexdigest()[:16]
        )
        self.rate_limiter = rate_limiter
        self._http = self._build_http_session()
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_status = RateLimitStatus()
        self._cache_status_lock = threading.Lock()
        self._last_cache_status: str | None = None

    @property
    def cache(self) -> Cache | None:
        """The response cache, or ``None`` if responses aren't cached."""
        return self._cache_coordinator.cache

    @cache.setter
    def cache(self, cache: Cache | None) -> None:
        # Validated by the coordinator, so a mis-wired cache fails now rather than on the
        # first request.
        self._cache_coordinator.cache = cache

    @staticmethod
    def _build_http_session() -> requests.Session:
        """Build the ``requests.Session`` that pools connections across API calls.

        Reusing one session keeps TCP/TLS connections to Metron alive between requests
        instead of paying a fresh handshake each time. Credentials are still sent per
        request, and cookies are refused outright so a stray ``Set-Cookie`` from the
        server can't turn later requests into session-authenticated ones.
        """
        http_session = requests.Session()
        # Only one host is ever contacted, so a single pool is enough; its size is what
        # bounds how many concurrent threads can reuse a connection.
        for prefix in ("https://", "http://"):
            http_session.mount(
                prefix,
                HTTPAdapter(pool_connections=1, pool_maxsize=HTTP_POOL_MAXSIZE),
            )
        http_session.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))
        return http_session

    def close(self) -> None:
        """Close the pooled HTTP connections held by this session.

        Calling this is optional. ``requests.Session`` has no finalizer of its own, so
        without it the sockets are only released when they are finalized (promptly under
        CPython's reference counting, but not guaranteed elsewhere), and Python may emit a
        ``ResourceWarning`` for each one. It is safe to call more than once, and the session
        can still be used afterwards, at the cost of opening new connections.

        Only the HTTP connections are closed. A ``cache`` or ``rate_limiter`` passed to the
        constructor is left untouched, since the caller owns it and may share it with other
        sessions; ``SqliteCache`` in particular keeps its database connection open.
        """
        self._http.close()

    def __enter__(self) -> Self:
        """Enter the context manager, returning this session."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, closing pooled connections."""
        self.close()

    @property
    def rate_limit_status(self) -> RateLimitStatus:
        """Return the most recently observed rate-limit state.

        Populated from the ``X-RateLimit-*`` headers Metron sends with every
        response. Fields are ``None`` until the first request completes, or if
        Metron did not report that window.
        """
        with self._rate_limit_lock:
            return self._rate_limit_status

    @property
    def last_cache_status(self) -> str | None:
        """Return the ``X-Cache`` value from the most recent response, if any.

        Metron reports whether a response was served from its cache (``"HIT"``)
        or generated fresh (``"MISS"``) via the ``X-Cache`` header, but only on
        endpoints that are actually cached — others omit the header entirely.
        This is ``None`` until the first request completes, and also resets to
        ``None`` after any request whose endpoint isn't cached, so it always
        reflects only the most recently completed request rather than a stale
        value from an earlier, cached one.
        """
        with self._cache_status_lock:
            return self._last_cache_status

    def _get(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
        *,
        kind: CacheKind = "detail",
    ) -> dict[str, Any]:
        """Send a GET request to the specified endpoint with optional parameters.

        This internal method handles GET requests with caching support. It first checks
        the cache for existing data, and if not found, makes the API request and caches
        the result for future use.

        Args:
            endpoint: List of path segments to build the API endpoint URL.
            params: Optional query parameters to include in the request.
            kind: Whether the endpoint returns a single object (``"detail"``) or a
                list (``"list"``), passed to the cache along with the resource name.

        Returns:
            dict[str, Any]: The response data from the API.

        Raises:
            ApiError: If the API returns an error response or if there are network issues.
        """
        return self._fetch(endpoint, params, kind=kind)[0]

    def _fetch(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
        *,
        kind: CacheKind = "detail",
        use_cache: bool = True,
        resource: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Do the work of ``_get``, also reporting whether the response came from the cache.

        Args:
            endpoint: List of path segments to build the API endpoint URL.
            params: Optional query parameters to include in the request.
            kind: ``"detail"`` or ``"list"``, passed to the cache with the resource name.
            use_cache: Whether to look in the cache first. The response is stored either way.
            resource: The resource the response is cached under. Defaults to the endpoint's
                first segment.

        Returns:
            The response data, and ``True`` if it was served from the cache.

        Raises:
            ApiError: If the API returns an error response or if there are network issues.
        """
        if params is None:
            params = {}

        # Sorted so the same query gets the same key whatever order its params were given in.
        cache_params = f"?{urlencode(sorted(params.items()))}" if params else ""

        url = self._url(endpoint)
        cache_key = f"{url}{cache_params}"
        resource = resource or str(endpoint[0])

        if use_cache:
            cached_response = self._cache_coordinator.get(cache_key, resource)
            if cached_response is not None:
                return cached_response, True

        invalidations = self._cache_coordinator.invalidation_count(resource)
        data = self._request_data("GET", url, params)
        self._cache_coordinator.store(cache_key, data, resource, kind, invalidations=invalidations)

        return data, False

    def _url(self, endpoint: list[str | int]) -> str:
        """Return the API URL for ``endpoint``'s path segments."""
        return self.api_url.format("/".join(str(e) for e in endpoint))

    def _send(
        self,
        method: str,
        endpoint: list[str | int],
        data: _Payload,
        *,
        also_invalidates: tuple[str, ...] = (),
        tags: _WriteTags | None = None,
    ) -> Any:
        """Send a write request with a body and return its parsed JSON response.

        Args:
            method: HTTP method to use ("POST" or "PATCH").
            endpoint: List of path segments to build the API endpoint URL.
            data: The data object to send in the request body.
            also_invalidates: Other cached resources the write changes (see ``_execute_write``).
            tags: Which of the resource's cached entries the write changes (see
                ``_execute_write``).

        Returns:
            Any: The response data from the API.

        Raises:
            ApiError: If there is an error during the API call.
        """
        response = self._execute_write(
            method, endpoint, data, also_invalidates=also_invalidates, tags=tags
        )
        return self._handle_http_response(response)

    def _execute_write(
        self,
        method: str,
        endpoint: list[str | int],
        data: _Payload | None,
        *,
        also_invalidates: tuple[str, ...] = (),
        tags: _WriteTags | None = None,
    ) -> requests.Response:
        """Send a write request, then drop cached entries it may have made stale.

        Args:
            method: HTTP method to use ("POST", "PATCH" or "DELETE").
            endpoint: List of path segments to build the API endpoint URL.
            data: The data to send in the request body, or ``None``.
            also_invalidates: Cached resources the write changes besides the one it's sent
                to (the endpoint's first segment), such as ``issue`` for a credit.
            tags: Given the response, or ``None`` if there isn't one, returns the tags of
                the entries of the resource it's sent to that the write may have made stale
                (see ``Cache``), or ``None`` for all of them. All are dropped if not given,
                and every entry of ``also_invalidates`` always is.

        Returns:
            The HTTP response, not yet checked for errors.

        Raises:
            ApiError: For connection errors or timeouts.
            RateLimitError: When the API rate limit is exceeded.
            RateLimiterError: If an injected ``rate_limiter`` object is missing a required method.
        """
        url = self._url(endpoint)
        LOGGER.debug("Request Method: %s | URL: %s", method, url)
        header, files, data_dict = self._prepare_request_payload(data)
        # Acquired separately from the send, so a write the limiter refuses (or fails on)
        # is known never to have been sent and leaves the cache alone.
        self._acquire_rate_limit_slot()
        response = None
        try:
            response = self._send_http_request(
                method, url, headers=header, data=data_dict, files=files
            )
            return response
        finally:
            # A 4xx means Metron rejected the write. Anything else, even a timeout or a 5xx,
            # may have been applied, and dropping the entries only costs a refetch.
            rejected = response is not None and (
                HTTPStatus.BAD_REQUEST <= response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
            )
            if not rejected:
                resource = str(endpoint[0])
                written_tags = None if tags is None else tags(response)
                self._cache_coordinator.invalidate(
                    (resource, *also_invalidates),
                    tags=None if written_tags is None else {resource: written_tags},
                )

    @staticmethod
    def _validate_response(resp: dict[str, Any], adapter_class: type) -> Any:
        """Validate API response using the provided Pydantic adapter class.

        This method ensures that the API response conforms to the expected schema
        by validating it against the appropriate Pydantic model.

        Args:
            resp: The response dictionary from the API to validate.
            adapter_class: The Pydantic type adapter class for validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If validation fails due to schema mismatch.
        """
        try:
            return _type_adapter(adapter_class).validate_python(resp)
        except ValidationError as error:
            raise ApiError(error) from error

    @classmethod
    def _validate_list_response(cls, resp: dict[str, Any], item_class: type) -> list[Any]:
        """Validate API response containing a list of items.

        This method validates paginated responses that contain a 'results' field
        with a list of items that should conform to the specified schema.

        Args:
            resp: The response dictionary containing a 'results' field with list data.
            item_class: The class type that each item in the list should conform to.

        Returns:
            list[Any]: The validated list of objects.

        Raises:
            ApiError: If validation fails for any item in the list.
        """
        return cls._validate_response(resp["results"], list[item_class])

    def _send_void(
        self,
        method: str,
        endpoint: list[str | int],
        data: BaseModel | None = None,
        *,
        also_invalidates: tuple[str, ...] = (),
    ) -> None:
        """Send a request that returns no response body (204 No Content or 200 with no body).

        Args:
            method: HTTP method to use ("POST" or "DELETE").
            endpoint: List of path segments to build the API endpoint URL.
            data: Optional data to send in the request body.
            also_invalidates: Other cached resources the write changes (see ``_execute_write``).

        Raises:
            ApiError: If the request fails.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        response = self._execute_write(method, endpoint, data, also_invalidates=also_invalidates)
        self._raise_for_status(response)

    def _handle_write_request(  # noqa: PLR0913
        self,
        method: str,
        endpoint: list[str | int],
        data: _Payload,
        response_class: type,
        *,
        also_invalidates: tuple[str, ...] = (),
        tags: _WriteTags | None = None,
    ) -> Any:
        """Handle POST or PATCH request with consistent error handling and validation.

        This internal method provides a standardized way to handle write requests
        (POST and PATCH) with proper response validation.

        Args:
            method: HTTP method to use ("POST" or "PATCH").
            endpoint: The API endpoint path segments.
            data: The data to send in the request.
            response_class: The expected response class for validation.
            also_invalidates: Other cached resources the write changes (see ``_execute_write``).
            tags: Which of the resource's cached entries the write changes (see
                ``_execute_write``).

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If the request fails or validation fails.
        """
        resp = self._send(method, endpoint, data, also_invalidates=also_invalidates, tags=tags)
        return self._validate_response(resp, response_class)

    # Generic resource methods
    def _get_resource(
        self,
        resource_name: str,
        _id: int,
        response_class: type,
        if_modified_since: datetime | None = None,
    ) -> Any:
        """Retrieve a single resource by ID.

        When ``if_modified_since`` is provided the request includes an
        ``If-Modified-Since`` header and may return ``None`` (304 Not Modified).
        Otherwise the regular cache-aware flow is used.

        Args:
            resource_name: The name of the resource endpoint (e.g., 'creator', 'character').
            _id: The unique identifier for the resource.
            response_class: The Pydantic model class for response validation.
            if_modified_since: Optional datetime; when given, the server may return
                304 Not Modified and this method returns ``None``.

        Returns:
            The validated resource object, or ``None`` when a 304 is received.

        Raises:
            ApiError: If the resource is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        if if_modified_since is not None:
            # Conditional requests skip the cache, which can't answer "has it changed?".
            data = self._request_data(
                "GET", self._url([resource_name, _id]), if_modified_since=if_modified_since
            )
            return None if data is None else self._validate_response(data, response_class)

        resp = self._get([resource_name, _id])
        return self._validate_response(resp, response_class)

    def _post_resource(self, resource_name: str, data: BaseModel, response_class: type) -> Any:
        """Create a new resource in the database.

        Generic method for creating any resource type via POST request.

        Args:
            resource_name: The name of the resource endpoint (e.g., 'creator', 'character').
            data: The data object to send in the POST request.
            response_class: The Pydantic model class for response validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        # Only lists the new object may join are dropped.
        return self._handle_write_request(
            "POST", [resource_name], data, response_class, tags=_created_tags(resource_name)
        )

    def _patch_resource(
        self, resource_name: str, _id: int, data: BaseModel, response_class: type
    ) -> Any:
        """Update an existing resource in the database.

        Generic method for updating any resource type via PATCH request.

        Args:
            resource_name: The name of the resource endpoint (e.g., 'creator', 'character').
            _id: The unique identifier for the resource to update.
            data: The data object to send in the PATCH request.
            response_class: The Pydantic model class for response validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        # Only entries the update may change are dropped. None values aren't sent (see
        # _prepare_request_payload), so they don't change anything.
        tags = update_tags(resource_name, _id, data.model_dump(exclude_none=True))
        return self._handle_write_request(
            "PATCH", [resource_name, _id], data, response_class, tags=lambda _response: tags
        )

    def _list_resources(
        self, resource_name: str, params: dict[str, str | int] | None, response_class: type
    ) -> list[Any]:
        """Retrieve a list of resources with optional filtering.

        Generic method for listing any resource type with pagination support.

        Args:
            resource_name: The name of the resource endpoint (e.g., 'creator', 'character').
            params: Optional dictionary of query parameters for filtering results.
            response_class: The Pydantic model class for validating list items.

        Returns:
            list[Any]: A list of validated resource objects.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get_results([resource_name], params)
        return self._validate_list_response(resp, response_class)

    def _get_resource_issues(self, resource_name: str, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues associated with a specific resource.

        Generic method for getting issue lists for characters, teams, arcs, or series.

        Args:
            resource_name: The name of the resource endpoint (e.g., 'character', 'team', 'arc').
            _id: The unique identifier for the resource.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        # A list of issues, so it's cached as issues: its TTL is the issue TTL, and an issue
        # write invalidates it.
        resp = self._get_results(
            [resource_name, _id, "issue_list"], resource=ResourceEndpoint.ISSUE
        )
        return self._validate_list_response(resp, BaseIssue)

    def _get_results(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
        *,
        resource: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve results from the specified API endpoint with automatic pagination handling.

        This internal method handles paginated responses by automatically following 'next' links
        to retrieve all available results. It's used by list methods to ensure complete data retrieval.

        A paginated list is served either entirely from the cache or entirely from Metron,
        so it's never a mix of pages from an older listing and a newer one: a fresh first
        page means every following page is fetched too, and a cached first page is only
        used if every other page of the list is cached as well. Otherwise the whole list is
        fetched again, starting from the first page requested.

        Args:
            endpoint: List of path segments to build the API endpoint URL.
            params: Optional query parameters to include in the request.
            resource: The resource every page is cached under. Defaults to the endpoint's
                first segment.

        Returns:
            dict[str, Any]: The complete response data with all paginated results combined.
        """
        if params is None:
            params = {}

        resource = resource or str(endpoint[0])
        result, from_cache = self._fetch(endpoint, params, kind="list", resource=resource)
        if from_cache:
            if (cached := self._cached_pages(result, resource)) is not None:
                return cached
            result, _ = self._fetch(
                endpoint, params, kind="list", use_cache=False, resource=resource
            )
        if not result["next"]:
            return result
        return self._retrieve_all_results(result, resource)

    def _cached_pages(self, data: dict[str, Any], resource: str) -> dict[str, Any] | None:
        """Add every following page of ``data`` from the cache, without making any requests.

        The pages before ``data`` must be cached too, though their results aren't added. A
        write drops only the pages holding the objects it changes, so an object that moves
        to another page (e.g. when renamed) shifts the pages between them without dropping
        them. Only a list whose every page is cached is known to have none dropped.

        Args:
            data: The first page requested, from the cache. It isn't modified, since the
                cache may have returned the very object it stores.
            resource: The resource name the first page was cached under.

        Returns:
            A copy of ``data`` with every following page's results, or ``None`` if any page
            of the list isn't in the cache.
        """
        previous_page = data.get("previous")
        while previous_page:
            page = self._cache_coordinator.get(previous_page, resource)
            if page is None:
                return None
            previous_page = page.get("previous")
        results = list(data["results"])
        next_page = data["next"]
        while next_page:
            page = self._cache_coordinator.get(next_page, resource)
            if page is None:
                return None
            results.extend(page["results"])
            next_page = page["next"]
        return {**data, "results": results}

    def _retrieve_all_results(self, data: dict[str, Any], resource: str) -> dict[str, Any]:
        """Retrieve all results from paginated data by following 'next' links.

        This internal method handles the pagination logic by making additional requests
        to fetch all pages of results. Every page is fetched from Metron rather than read
        from the cache (see ``_get_results``), then stored. It respects rate limiting.

        Args:
            data: Dictionary containing the initial response data with pagination information.
                It isn't modified, since the cache may have stored the very same object.
            resource: The resource name the first page was cached under; every
                following page is cached under the same one, as a ``"list"``.

        Returns:
            dict[str, Any]: A copy of ``data`` containing all results retrieved by following
                pagination links.

        Raises:
            RateLimitError: If a page can't be fetched despite retrying (see ``_fetch_page``).
        """
        results = list(data["results"])
        next_page = data["next"]

        while next_page:
            response, invalidations = self._fetch_page(next_page, resource)
            results.extend(response["results"])
            self._cache_coordinator.store(
                next_page, response, resource, "list", invalidations=invalidations
            )
            next_page = response["next"]

        return {**data, "results": results}

    def _fetch_page(self, url: str, resource: str) -> tuple[dict[str, Any], int]:
        """Fetch one page of a paginated list, retrying it when Metron rate-limits it.

        Only this page is retried, rather than letting the error propagate and restart
        the entire paginated fetch from page 1.

        Args:
            url: The page's URL, a previous page's ``next`` link.
            resource: The resource the page is cached under.

        Returns:
            The page's parsed response, and ``resource``'s ``invalidation_count`` from
            just before the attempt that fetched it, to pass to ``store``.

        Raises:
            RateLimitError: If the page is rejected with a 429 more than
                ``MAX_RATE_LIMIT_RETRIES`` times in a row, or more than
                ``MAX_UNTIMED_RATE_LIMIT_RETRIES`` times in a row when it has no
                ``Retry-After``, or, when a ``rate_limiter`` is set, if the limiter itself
                refuses a request (its daily window is exhausted).
        """
        untimed_retries = 0
        limited_retries = 0
        while True:
            # Read before every attempt, not once per page: a write made while a retry
            # waits is from before the page that's then fetched, so it can't be stale.
            invalidations = self._cache_coordinator.invalidation_count(resource)
            try:
                return self._request_data("GET", url), invalidations
            except RateLimitError as e:
                # A rate limiter that refuses the request itself (an exhausted daily window)
                # is deliberately not waited out here: the caller decides whether to wait.
                if self.rate_limiter is not None and not isinstance(e, _ServerRateLimitError):
                    raise
                # A missing Retry-After (0) can't be waited out, so don't retry it forever.
                untimed_retries = untimed_retries + 1 if e.retry_after <= 0 else 0
                limited_retries += 1
                if (
                    untimed_retries > MAX_UNTIMED_RATE_LIMIT_RETRIES
                    or limited_retries > MAX_RATE_LIMIT_RETRIES
                ):
                    raise
                if self.rate_limiter is None:
                    # Floor a missing Retry-After at the burst window, as the limiter does,
                    # so the capped retries are still spaced out rather than back-to-back.
                    delay = e.retry_after if e.retry_after > 0 else DEFAULT_BURST_PERIOD
                    LOGGER.warning("Rate limit during pagination; retrying page in %ss", delay)
                    time.sleep(delay)
                else:
                    # The limiter has already backed off from this 429; acquire() blocks.
                    LOGGER.warning("Rate limit during pagination; retrying page via rate limiter")

    def _prepare_request_payload(
        self, data: _Payload | None
    ) -> tuple[dict[str, str], dict[str, tuple[str, bytes]] | None, str | dict[str, Any] | None]:
        """Prepare request payload, handling data serialization and file uploads.

        Args:
            data: Optional data to include in the request body.

        Returns:
            tuple: A tuple of (header, files, body) where header contains HTTP headers,
                  files contains file uploads, and body is the request body: a JSON string,
                  multipart form fields, or ``None``.
        """
        header = self.header.copy()
        files = None
        body: str | dict[str, Any] | None = None

        if isinstance(data, list):
            # Handle list data (e.g., credits)
            body = json.dumps([item.model_dump() for item in data])
        elif data is not None:
            fields = data.model_dump()
            # Endpoints whose model has an `image` field (creator, issue, team, character,
            # arc) require multipart/form-data even when no file is present. The others
            # (series, universe, etc.) require JSON.
            if "image" in fields:
                files, body = _multipart_payload(fields)
            else:
                # None values are stripped so PATCH requests don't overwrite existing data
                # with nulls.
                body = json.dumps({k: v for k, v in fields.items() if v is not None}, default=str)

        if isinstance(body, str):
            header["Content-Type"] = _JSON_CONTENT_TYPE

        LOGGER.debug("Header: %s", header)
        LOGGER.debug("Data: %s", body)

        return header, files, body

    def _execute_http_request(  # noqa: PLR0913
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        data: str | dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes]] | None = None,
    ) -> requests.Response:
        """Execute the HTTP request with proper error handling.

        Args:
            method: HTTP method to use ("GET", "POST", "PATCH" or "DELETE").
            url: The complete URL to send the request to.
            params: Optional query parameters to include in the request.
            headers: HTTP headers to send with the request. Defaults to ``self.header``.
            data: The request body (see ``_prepare_request_payload``), or ``None``.
            files: Optional file uploads.

        Returns:
            requests.Response: The HTTP response object.

        Raises:
            ApiError: For connection errors or timeouts.
            RateLimitError: When the API rate limit is exceeded (either locally or by the server).
            RateLimiterError: If an injected ``rate_limiter`` object is missing a required method.
        """
        self._acquire_rate_limit_slot()
        return self._send_http_request(
            method, url, params=params, headers=headers, data=data, files=files
        )

    def _send_http_request(  # noqa: PLR0913
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        data: str | dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes]] | None = None,
    ) -> requests.Response:
        """Send the HTTP request in a rate-limit slot already acquired, then release it.

        Only ``_execute_http_request`` and ``_execute_write`` call this, each right
        after ``_acquire_rate_limit_slot``. Anything raised before this is called means
        the request was never sent.

        Args:
            method: HTTP method to use ("GET", "POST", "PATCH" or "DELETE").
            url: The complete URL to send the request to.
            params: Optional query parameters to include in the request.
            headers: HTTP headers to send with the request. Defaults to ``self.header``.
            data: The request body (see ``_prepare_request_payload``), or ``None``.
            files: Optional file uploads.

        Returns:
            requests.Response: The HTTP response object.

        Raises:
            ApiError: For connection errors or timeouts.
            RateLimiterError: If an injected ``rate_limiter`` object is missing a required method.
        """
        # The slot is held from here on, so it must be released on every exit path, not just
        # the connection errors we translate. ``status`` stays ``None`` unless the response
        # reported rate-limit headers and they were folded into the session's state.
        status: RateLimitStatus | None = None
        try:
            response = self._http.request(
                method,
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                auth=self._auth,
                headers=self.header if headers is None else headers,
                data=data,
                files=files,
            )
            status = self._update_rate_limit_status(response.headers)
            self._update_cache_status(response.headers)
            if response.status_code == requests.codes.too_many:
                self._report_rate_limited(self._retry_after_seconds(response))
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as err:
            msg = f"Connection error: {err!r}"
            raise ApiError(msg) from err
        finally:
            self._release_rate_limit_slot(status)
        return response

    def _handle_http_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle HTTP response, parsing JSON and checking for errors.

        Args:
            response: The HTTP response object to process.

        Returns:
            dict[str, Any]: The parsed JSON response data.

        Raises:
            RateLimitError: When the API rate limit is exceeded.
            ApiError: For HTTP errors, invalid JSON, or API error responses.
        """
        self._raise_for_status(response)

        try:
            resp = response.json()
        except ValueError as err:
            msg = f"Invalid JSON response: {err!r}"
            raise ApiError(msg) from err

        if "detail" in resp:
            raise ApiError(resp["detail"])

        return resp

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        """Raise the error for an unsuccessful (4xx or 5xx) response.

        Args:
            response: The HTTP response to check.

        Raises:
            RateLimitError: For a 429, as a ``_ServerRateLimitError``.
            ApiError: For any other HTTP error.
        """
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            if response.status_code == requests.codes.too_many:
                retry_after = _SessionCore._retry_after_seconds(response)
                msg = (
                    f"Metron API Rate Limit exceeded, need to wait for {format_time(retry_after)}."
                )
                raise _ServerRateLimitError(msg, retry_after=retry_after) from err
            msg = f"HTTP error: {err!r} | Response body: {response.text}"
            raise ApiError(msg) from err

    def _update_rate_limit_status(self, headers: Mapping[str, str]) -> RateLimitStatus | None:
        """Update the session's rate-limit state from a response's headers.

        Returns:
            The updated state, as merged under the lock, so the caller gets this
            response's headers even if another thread updates the state right after.
            ``None`` if the response reported no rate-limit headers, so the previous
            response's state isn't passed on as this one's.
        """
        with self._rate_limit_lock:
            merged = self._rate_limit_status.merge_headers(headers)
            if merged is self._rate_limit_status:
                return None
            self._rate_limit_status = merged
            return merged

    def _update_cache_status(self, headers: Any) -> None:
        """Update the session's last-observed ``X-Cache`` status from response headers.

        Unlike rate-limit headers, ``X-Cache`` is per-endpoint: Metron only adds it
        on the paths that actually go through its response cache and omits it
        entirely elsewhere. So a missing header resets the status to ``None``
        rather than preserving a stale value from a previous, cached endpoint.
        """
        with self._cache_status_lock:
            self._last_cache_status = headers.get(HEADER_CACHE)

    def _acquire_rate_limit_slot(self) -> None:
        """Dispatch to the injected rate limiter, or fall back to the fail-fast check.

        This is the single choke point for rate limiting: every HTTP send
        goes through ``_execute_http_request``, which calls this first. When
        no ``rate_limiter`` is configured, behavior is identical to calling
        ``_check_rate_limit()`` directly.

        Raises:
            RateLimitError: When ``rate_limiter`` is unset and the last known
                rate-limit headers show a window is exhausted and hasn't reset yet.
            RateLimiterError: If ``rate_limiter`` is set but is missing a required method.
        """
        if self.rate_limiter is None:
            self._check_rate_limit()
            return
        self._rate_limiter_method("acquire")(self.rate_limit_status)

    def _rate_limiter_method(self, name: str) -> Callable[..., None]:
        """Look up a required method on the injected rate limiter.

        Only the lookup is guarded, so an ``AttributeError`` raised from inside the
        limiter's own code isn't misreported as a missing method.

        Raises:
            RateLimiterError: If the rate limiter has no attribute ``name``.
        """
        try:
            return getattr(self.rate_limiter, name)
        except AttributeError as e:
            msg = f"Rate limiter object passed in is missing attribute: {e!r}"
            raise RateLimiterError(msg) from e

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float:
        """Return the response's ``Retry-After`` value in seconds, or 0 if it has none."""
        return float(response.headers.get("Retry-After", 0))

    def _report_rate_limited(self, retry_after: float) -> None:
        """Tell the injected rate limiter, if any, that Metron rejected a request with a 429.

        Args:
            retry_after: The response's ``Retry-After`` in seconds, or 0 if it had none.

        Raises:
            RateLimiterError: If ``rate_limiter`` is set but is missing a required method.
        """
        if self.rate_limiter is None:
            return
        on_rate_limited = self._rate_limiter_method("on_rate_limited")
        # The 429 is still reported to the caller as a RateLimitError, so a limiter that
        # fails to record it (e.g. its backing store is unreachable) is logged, not raised.
        try:
            on_rate_limited(retry_after)
        except Exception:
            LOGGER.exception("Rate limiter on_rate_limited() failed; ignoring")

    def _release_rate_limit_slot(self, status: RateLimitStatus | None) -> None:
        """Release the slot reserved by ``_acquire_rate_limit_slot``, if a limiter is set.

        Args:
            status: The freshly updated rate-limit status after the request
                completed, or ``None`` if it failed before headers were received or
                the response reported no rate-limit headers.

        Raises:
            RateLimiterError: If ``rate_limiter`` is set but is missing a required method.
        """
        if self.rate_limiter is None:
            return
        release = self._rate_limiter_method("release")
        # This runs in a ``finally``, so raising here would discard a successful response
        # or mask the request's own error; log a failing limiter instead.
        try:
            release(status)
        except Exception:
            LOGGER.exception("Rate limiter release() failed; ignoring")

    def _check_rate_limit(self) -> None:
        """Check rate limits before making a request.

        Metron's sustained (daily) limit varies per user based on OpenCollective
        donor tier, so mokkari doesn't track it locally with a fixed quota.
        Instead it trusts the most recently observed ``X-RateLimit-*`` response
        headers, and only pre-empts a request once those headers show a window
        is already exhausted.

        Not synchronized with request dispatch: this check and the subsequent
        HTTP call are not serialized under a shared lock, so under concurrent
        callers (e.g. multiple threads sharing one ``Session``) more than one
        caller can pass this check before either request's response updates
        ``rate_limit_status``. See the "Thread safety" note on ``Session`` for
        guidance on bounding your own concurrency.

        Raises:
            RateLimitError: When the last known rate-limit headers show the
                burst or sustained window is exhausted and hasn't reset yet. Its
                ``retry_after`` is the time until the reset Metron reported, measured
                against the local clock.
        """
        error = self.rate_limit_status.exhausted_error(datetime.now(UTC))
        if error is None:
            return
        LOGGER.warning("%s", error)
        raise error

    def _request_data(
        self,
        method: str,
        url: str,
        params: dict[str, str | int] | None = None,
        *,
        if_modified_since: datetime | None = None,
    ) -> Any:
        """Send a request without a body and return its parsed JSON response.

        Writes, which send a body, go through ``_execute_write`` instead.

        Args:
            method: HTTP method to use (normally "GET").
            url: The complete URL to send the request to.
            params: Optional query parameters to include in the request.
            if_modified_since: If given, sent as ``If-Modified-Since`` (a naive datetime
                is taken as UTC), so Metron can answer 304 Not Modified when the data
                hasn't changed since.

        Returns:
            Any: The parsed JSON response from the API, or ``None`` for a 304 answering
                ``if_modified_since``.

        Raises:
            ApiError: For connection errors, HTTP errors, or invalid JSON responses.
            RateLimitError: When the API rate limit is exceeded (either locally or by the server).
        """
        headers = self.header
        if if_modified_since is not None:
            headers = {**headers, "If-Modified-Since": _http_date(if_modified_since)}
        LOGGER.debug("Request Method: %s | URL: %s | Params: %s", method, url, params)
        LOGGER.debug("Header: %s", headers)
        response = self._execute_http_request(method, url, params=params, headers=headers)
        if if_modified_since is not None and response.status_code == HTTPStatus.NOT_MODIFIED:
            return None
        return self._handle_http_response(response)


class Session(
    _SessionCore,
    CatalogEndpoints,
    ReadingListEndpoints,
    CollectionEndpoints,
    PullListEndpoints,
    WishListEndpoints,
):
    """A comprehensive API client for interacting with the Metron Comics Database.

    The Session class provides a complete interface for accessing comic book data including
    creators, characters, publishers, series, issues, teams, arcs, and more. It handles
    authentication, rate limiting, caching, and response validation automatically.

    Metron enforces two rate-limit windows:

    - A burst limit of at least 20 requests per minute for every user. The server
      raises it above that floor when load allows, so read it from the headers.
    - A sustained daily limit that starts at 5,000 requests, and is raised for
      OpenCollective donors (up to 25,000/day for the highest tier). Because
      this limit varies per user and can change at any time, Session does not
      track it locally with a fixed quota. Instead it reads the
      ``X-RateLimit-*`` headers Metron returns with every response and only
      pre-empts a request once those headers show the current window is
      exhausted (see ``rate_limit_status``).

    **Important**: When rate limits are exceeded, a RateLimitError is raised immediately
    without making the API request. Applications must catch and handle this exception
    appropriately (see examples below).

    **Thread safety**: A single ``Session`` can be shared across threads. By default its
    pre-emptive rate-limit check is advisory, not a hard gate: it only raises once the
    *last known* response headers show a window is exhausted, and that check isn't
    serialized with sending the request. Concurrent threads can each pass the check and
    send their requests before a response comes back to update ``rate_limit_status``, so
    a burst of threads can momentarily exceed the per-minute limit before local state
    catches up (Metron's server-side limit is still authoritative and will reject the
    excess requests). If you're calling a shared ``Session`` from multiple threads without
    a ``rate_limiter``, cap your own concurrency rather than relying on ``Session`` to do
    it for you — e.g. bound a ``ThreadPoolExecutor`` at or below the burst limit, or gate
    requests with a ``threading.Semaphore``. Passing a ``rate_limiter`` (see ``Args``)
    closes this gap: every HTTP send is dispatched through it instead, so it can block
    concurrent callers until capacity actually frees rather than letting them race.

    Features:

    - Automatic authentication with a Bearer API token
    - Rate limiting driven by Metron's response headers, with clear error messages
    - Optional SQLite caching for improved performance
    - Comprehensive error handling and validation
    - Support for both read and write operations (write operations require admin permissions)
    - Automatic pagination handling for large result sets
    - Image upload support for certain endpoints
    - Development mode for testing against a local instances of Metron.

    Args:
        api_token: API token for Bearer-token authentication.
        cache: Optional response cache (e.g. ``SqliteCache``) to avoid repeat requests.
        user_agent: Optional custom user agent string to append to the default user agent.
        dev_mode: If True, connects to local development instance at 127.0.0.1:8000 instead of production.
        rate_limiter: Optional pacing gate to dispatch every HTTP send
            through, in place of the default fail-fast check. See
            :class:`mokkari.rate_limit.RateLimiter`. Defaults to ``None``,
            which preserves the default raise-immediately behavior exactly.

    Attributes:
        api_token (str): The API token used for Bearer-token authentication.
        header (dict): HTTP headers sent with each request, including User-Agent.
        api_url (str): The base URL for API requests (production or development).
        cache (SqliteCache | None): The cache instance if provided.
        rate_limiter (RateLimiter | None): The injected pacing gate, if provided.
        rate_limit_status (RateLimitStatus): The most recently observed rate-limit
            state, parsed from Metron's response headers.
        last_cache_status (str | None): The ``X-Cache`` value ("HIT" or "MISS")
            from the most recently completed response, or ``None`` if that
            endpoint isn't cached and so didn't report one.

    Examples:
        Basic usage:
        >>> session = Session("your-api-token")
        >>> issue = session.issue(1)
        >>> print(issue)

        With caching:
        >>> from mokkari.sqlite_cache import SqliteCache
        >>> cache = SqliteCache("cache.db")
        >>> session = Session("your-api-token", cache=cache)

        Development mode:
        >>> session = Session("your-api-token", dev_mode=True)

        Handling rate limits - simple retry:
        >>> import time
        >>> from mokkari.exceptions import RateLimitError
        >>> from mokkari.utils import format_time
        >>> session = Session("your-api-token")
        >>> try:
        ...     issue = session.issue(1)
        ... except RateLimitError as e:
        ...     print(f"Rate limited: {e}")
        ...     print(f"Waiting {format_time(e.retry_after)}...")
        ...     time.sleep(e.retry_after)
        ...     issue = session.issue(1)  # Retry after waiting; may raise again, see below

        ``retry_after`` is when the next slot frees. Another client sharing your account can
        take it first, so the retry can raise ``RateLimitError`` again, which is why the loop
        below keeps retrying.

        Handling minute vs daily rate limits:
        >>> import time
        >>> from mokkari.exceptions import RateLimitError
        >>> from mokkari.utils import format_time
        >>> session = Session("your-api-token")
        >>> def fetch_with_rate_limit_handling(issue_id):
        ...     while True:
        ...         try:
        ...             return session.issue(issue_id)
        ...         except RateLimitError as e:
        ...             if "per minute" in str(e):
        ...                 # Minute limit - automatically wait and retry
        ...                 print(f"{e}")
        ...                 print(f"Waiting {format_time(e.retry_after)}...")
        ...                 time.sleep(e.retry_after)
        ...                 continue
        ...             elif "per day" in str(e):
        ...                 # Daily limit - ask user whether to wait or quit
        ...                 response = input(f"Wait {format_time(e.retry_after)}? (y/n): ")
        ...                 if response.lower() == 'y':
        ...                     time.sleep(e.retry_after)
        ...                     continue
        ...                 else:
        ...                     raise
        ...             else:
        ...                 raise
        >>> issue = fetch_with_rate_limit_handling(1)

        Inspecting the current rate-limit state:
        >>> session = Session("your-api-token")
        >>> issue = session.issue(1)
        >>> status = session.rate_limit_status
        >>> print(f"Sustained remaining: {status.sustained.remaining}/{status.sustained.limit}")

        Pacing requests instead of raising, under concurrent use:
        >>> from mokkari.rate_limit import HeaderPacedRateLimiter
        >>> session = Session("your-api-token", rate_limiter=HeaderPacedRateLimiter())
        >>> issue = session.issue(1)  # blocks instead of raising if a window is exhausted

        Checking whether the last response was served from Metron's cache:
        >>> session = Session("your-api-token")
        >>> issue = session.issue(1)
        >>> print(session.last_cache_status)  # "HIT" or "MISS"

    Raises:
        AuthenticationError: If the api_token is missing or empty.
        ApiError: For general API errors, authentication failures, or network issues.
        RateLimitError: When API rate limits are exceeded (both local tracking and server-side).
        CacheError: If an injected ``cache`` object lacks a ``get`` or ``store`` method
            taking Session's arguments.
        RateLimiterError: If an injected ``rate_limiter`` object is missing a required method.
        ValidationError: For invalid response data that doesn't match expected schemas.
    """


if TYPE_CHECKING:
    # The endpoint mixins type-check against EndpointHelpers; fail here if Session stops
    # providing any of it.
    def _provides_endpoint_helpers(session: Session) -> EndpointHelpers:
        return session
