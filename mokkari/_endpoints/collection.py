"""Collection endpoints for ``Session``.

This module provides the following class:

- CollectionEndpoints: The authenticated user's collection.
"""

from __future__ import annotations

__all__ = ["CollectionEndpoints"]

from typing import TYPE_CHECKING, overload

from mokkari.cache import ResourceEndpoint
from mokkari.schemas.collection import (
    CollectionAddItem,
    CollectionList,
    CollectionRead,
    CollectionStats,
    CollectionUpdate,
    CollectionUpdateResponse,
    MissingIssue,
    MissingSeries,
    ScrobbleRequest,
    ScrobbleResponse,
)

if TYPE_CHECKING:
    from datetime import datetime

    from mokkari._endpoints._helpers import EndpointHelpers as _Base
else:
    _Base = object


class CollectionEndpoints(_Base):
    """The authenticated user's collection methods of ``Session``.

    A mixin: it relies on the request, cache and validation helpers of ``Session``
    (see ``EndpointHelpers``).
    """

    # Collection methods
    @overload
    def collection(self, _id: int, if_modified_since: None = None) -> CollectionRead: ...
    @overload
    def collection(self, _id: int, if_modified_since: datetime) -> CollectionRead | None: ...
    def collection(
        self, _id: int, if_modified_since: datetime | None = None
    ) -> CollectionRead | None:
        """Retrieve detailed information about a collection item by ID.

        Note: This endpoint requires authentication. Users can only access their own collection items.

        Args:
            _id: The unique identifier for the collection item.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A CollectionRead object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the collection item is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> collection_item = session.collection(1)
            >>> print(f"Issue: {collection_item.issue.series.name} #{collection_item.issue.number}")
        """
        return self._get_resource(
            ResourceEndpoint.COLLECTION, _id, CollectionRead, if_modified_since
        )

    def collections_list(self, params: dict[str, str | int] | None = None) -> list[CollectionList]:
        """Retrieve a list of collection items with optional filtering.

        Note: This endpoint requires authentication. Users can only access their own collection items.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include:
                   - 'book_format': Filter by format (PRINT, DIGITAL, BOTH)
                   - 'grade': Filter by comic book grade (CGC scale)
                   - 'grading_company': Filter by grading company (CGC, CBCS, PGX)
                   - 'is_read': Filter by read status (boolean)
                   - 'issue__series': Filter by series ID
                   - 'modified_gt': Filter by modification date (greater than)
                   - 'purchase_date': Filter by purchase date
                   - 'rating': Filter by star rating (1-5)

        Returns:
            list[CollectionList]: A list of CollectionList objects representing collection items.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> collection = session.collections_list({"is_read": False})
            >>> unread = [item for item in collection if not item.is_read]
        """
        return self._list_resources(ResourceEndpoint.COLLECTION, params, CollectionList)

    def collection_missing_issues(self, series_id: int) -> list[MissingIssue]:
        """Retrieve a list of missing issues for a specific series.

        Returns issues from a series that are not in the authenticated user's collection.

        Note: This endpoint requires authentication.

        Args:
            series_id: The unique identifier for the series.

        Returns:
            list[MissingIssue]: A list of MissingIssue objects representing issues
                               not in the user's collection.

        Raises:
            ApiError: If the series is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> missing = session.collection_missing_issues(1)
            >>> print(f"Missing {len(missing)} issues from this series")
        """
        resp = self._get_results([ResourceEndpoint.COLLECTION, "missing_issues", series_id])
        return self._validate_list_response(resp, MissingIssue)

    def collection_missing_series(self) -> list[MissingSeries]:
        """Retrieve a list of series where the user has some issues but is missing others.

        Returns series where the authenticated user owns at least one issue but not
        all issues in the series.

        Note: This endpoint requires authentication.

        Returns:
            list[MissingSeries]: A list of MissingSeries objects representing series
                                with incomplete collections.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> incomplete_series = session.collection_missing_series()
            >>> for series in incomplete_series:
            ...     print(f"Series: {series.name} ({series.year_began})")
        """
        resp = self._get_results([ResourceEndpoint.COLLECTION, "missing_series"])
        return self._validate_list_response(resp, MissingSeries)

    def collection_stats(self) -> CollectionStats:
        """Retrieve statistics about the authenticated user's collection.

        Returns comprehensive statistics including total items, total value,
        read/unread counts, and breakdowns by format.

        Note: This endpoint requires authentication.

        Returns:
            CollectionStats: A CollectionStats object containing collection statistics.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> stats = session.collection_stats()
            >>> print(f"Total items: {stats.total_items}")
            >>> print(f"Total value: {stats.total_value}")
            >>> print(f"Read: {stats.read_count}, Unread: {stats.unread_count}")
        """
        resp = self._get([ResourceEndpoint.COLLECTION, "stats"])
        return self._validate_response(resp, CollectionStats)

    def collection_scrobble(self, data: ScrobbleRequest) -> ScrobbleResponse:
        """Mark an issue as read (scrobble).

        This endpoint marks an issue as read and optionally provides a rating.
        If the issue is not already in the user's collection, it will be
        automatically added with default values.

        Note: This endpoint requires authentication. Users can only scrobble issues
        to their own collection.

        Args:
            data: ScrobbleRequest object containing the issue_id and optional
                  date_read and rating.

        Returns:
            ScrobbleResponse: A ScrobbleResponse object containing the updated
                            collection item information and a 'created' flag
                            indicating whether a new collection item was created.

        Raises:
            ApiError: If the issue is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> from datetime import datetime
            >>> scrobble_data = ScrobbleRequest(
            ...     issue_id=1,
            ...     date_read=datetime.now(),
            ...     rating=5
            ... )
            >>> result = session.collection_scrobble(scrobble_data)
            >>> print(f"Issue marked as read: {result.issue.series.name} #{result.issue.number}")
            >>> print(f"New item created: {result.created}")

            Mark as read without rating:
            >>> scrobble_data = ScrobbleRequest(issue_id=1)
            >>> result = session.collection_scrobble(scrobble_data)
        """
        return self._handle_write_request(
            "POST", [ResourceEndpoint.COLLECTION, "scrobble"], data, ScrobbleResponse
        )

    def collection_patch(self, _id: int, data: CollectionUpdate) -> CollectionUpdateResponse:
        """Update the rating of an existing collection item.

        Note: Users can only update items in their own collection. Only the rating field can be updated; read-tracking
        (is_read/date_read) is handled exclusively through the scrobble action.

        Args:
            _id: The unique identifier for the collection item to update.
            data: CollectionUpdate object containing the updated rating.

        Returns:
            CollectionUpdateResponse: The updated collection item's id, rating, and
                                       modified timestamp.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> update_data = CollectionUpdate(rating=4)
            >>> result = session.collection_patch(1, update_data)
            >>> print(f"Rating updated to: {result.rating}")
        """
        return self._patch_resource(
            ResourceEndpoint.COLLECTION, _id, data, CollectionUpdateResponse
        )

    def collection_add(self, data: CollectionAddItem) -> CollectionRead:
        """Add an issue to the authenticated user's collection.

        Note: This endpoint requires authentication.

        Args:
            data: CollectionAddItem object containing the issue_id and optional
                  quantity, grade, and purchase details.

        Returns:
            CollectionRead: The created (or updated, if the issue was already
                             in the collection) collection item.

        Raises:
            ApiError: If the issue is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> from mokkari.schemas.collection import CollectionAddItem
            >>> item = session.collection_add(CollectionAddItem(issue_id=1, quantity=2))
            >>> print(f"Added: {item.issue.series.name} #{item.issue.number}")
        """
        return self._handle_write_request(
            "POST", [ResourceEndpoint.COLLECTION, "add"], data, CollectionRead
        )

    def collection_delete(self, _id: int) -> None:
        """Remove an item from the authenticated user's collection.

        Note: Users can only remove items from their own collection.

        Args:
            _id: The unique identifier for the collection item to remove.

        Raises:
            ApiError: If the collection item is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> session.collection_delete(1)
        """
        self._send_void("DELETE", [ResourceEndpoint.COLLECTION, _id])
