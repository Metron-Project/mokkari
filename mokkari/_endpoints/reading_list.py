"""Reading list endpoints for ``Session``.

This module provides the following class:

- ReadingListEndpoints: Reading lists and their items.
"""

from __future__ import annotations

__all__ = ["ReadingListEndpoints"]

# Imported at runtime, not only for type checking, so typing.get_type_hints() can
# resolve the detail methods' if_modified_since annotations.
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, overload

from mokkari.cache import ResourceEndpoint
from mokkari.schemas.reading_list import ReadingListItem, ReadingListList, ReadingListRead

if TYPE_CHECKING:
    from mokkari._endpoints._helpers import EndpointHelpers as _Base
else:
    _Base = object


class ReadingListEndpoints(_Base):
    """Reading lists and their items methods of ``Session``.

    A mixin: it relies on the request, cache and validation helpers of ``Session``
    (see ``EndpointHelpers``).
    """

    # Reading List methods
    @overload
    def reading_list(self, _id: int, if_modified_since: None = None) -> ReadingListRead: ...
    @overload
    def reading_list(self, _id: int, if_modified_since: datetime) -> ReadingListRead | None: ...
    def reading_list(
        self, _id: int, if_modified_since: datetime | None = None
    ) -> ReadingListRead | None:
        """Retrieve detailed information about a reading list by ID.

        Note: This endpoint requires authentication. Users can access:
        - Authenticated users: Public lists + own lists
        - Admin users: Public lists + own lists + Metron's lists

        Args:
            _id: The unique identifier for the reading list.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A ReadingListRead object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the reading list is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(
            ResourceEndpoint.READING_LIST, _id, ReadingListRead, if_modified_since
        )

    def reading_lists_list(
        self, params: dict[str, str | int] | None = None
    ) -> list[ReadingListList]:
        """Retrieve a list of reading lists with optional filtering.

        Note: This endpoint requires authentication. Users can access:
        - Authenticated users: Public lists + own lists
        - Admin users: Public lists + own lists + Metron's lists

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include:
                   - 'name': Filter by reading list name
                   - 'user': Filter by user ID
                   - 'username': Filter by username
                   - 'is_private': Filter by privacy status (boolean)
                   - 'attribution_source': Filter by attribution source (CBRO, CMRO, CBH, etc.)
                   - 'modified_gt': Filter by modification date (greater than)

        Returns:
            list[ReadingListList]: A list of ReadingListList objects representing reading lists.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._list_resources(ResourceEndpoint.READING_LIST, params, ReadingListList)

    def reading_list_items(self, _id: int) -> list[ReadingListItem]:
        """Retrieve a paginated list of items for a specific reading list.

        Note: This endpoint requires authentication.

        Args:
            _id: The unique identifier for the reading list.

        Returns:
            list[ReadingListItem]: A list of ReadingListItem objects representing items
                                   in the reading list.

        Raises:
            ApiError: If the reading list is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get_results([ResourceEndpoint.READING_LIST, _id, "items"])
        return self._validate_list_response(resp, ReadingListItem)
