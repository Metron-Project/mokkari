"""Pull list endpoints for ``Session``.

This module provides the following class:

- PullListEndpoints: The authenticated user's pull list.
"""

from __future__ import annotations

__all__ = ["PullListEndpoints"]

from typing import TYPE_CHECKING

from mokkari.cache import ResourceEndpoint
from mokkari.schemas.pull_list import PullListAddSeries, PullListIssue, PullListRead, PullListSeries

if TYPE_CHECKING:
    from mokkari._endpoints._helpers import EndpointHelpers as _Base
else:
    _Base = object


class PullListEndpoints(_Base):
    """The authenticated user's pull list methods of ``Session``.

    A mixin: it relies on the request, cache and validation helpers of ``Session``
    (see ``EndpointHelpers``).
    """

    # Pull list methods
    def pull_list(self) -> PullListRead:
        """Retrieve the authenticated user's pull list.

        Note: This endpoint requires authentication.

        Returns:
            A PullListRead object.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> pl = session.pull_list()
            >>> print(f"Series: {pl.series_count}")
        """
        results = self._list_resources(ResourceEndpoint.PULL_LIST, None, PullListRead)
        return results[0]

    def pull_list_issues(self, params: dict[str, str | int] | None = None) -> list[PullListIssue]:
        """Retrieve issues for series on the authenticated user's pull list.

        Optionally filter by store date using store_date_after and store_date_before.

        Note: This endpoint requires authentication.

        Args:
            params: Optional dictionary of query parameters. Supports:
                - store_date_after: Return issues with a store date on or after this date (YYYY-MM-DD).
                - store_date_before: Return issues with a store date on or before this date (YYYY-MM-DD).

        Returns:
            list[PullListIssue]: A list of PullListIssue objects.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> issues = session.pull_list_issues({"store_date_after": "2024-01-01"})
            >>> for issue in issues:
            ...     print(f"{issue.series.name} #{issue.number}")
        """
        resp = self._get_results([ResourceEndpoint.PULL_LIST, "issues"], params)
        return self._validate_list_response(resp, PullListIssue)

    def pull_list_series(self, params: dict[str, str | int] | None = None) -> list[PullListSeries]:
        """Retrieve the series on the authenticated user's pull list.

        Note: This endpoint requires authentication.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[PullListSeries]: A list of PullListSeries objects.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> series_list = session.pull_list_series()
            >>> for entry in series_list:
            ...     print(entry.series.display_name)
        """
        resp = self._get_results([ResourceEndpoint.PULL_LIST, "series"], params)
        return self._validate_list_response(resp, PullListSeries)

    def pull_list_add_series(self, series_id: int) -> PullListSeries:
        """Add a series to the authenticated user's pull list.

        Note: This endpoint requires authentication.

        Args:
            series_id: The unique identifier of the series to add.

        Returns:
            PullListSeries: The pull list series entry.

        Raises:
            ApiError: If the series is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> entry = session.pull_list_add_series(42)
            >>> print(entry.series.display_name)
        """
        return self._handle_write_request(
            "POST",
            [ResourceEndpoint.PULL_LIST, "series", "add"],
            PullListAddSeries(series_id=series_id),
            PullListSeries,
        )

    def pull_list_remove_series(self, series_pk: int) -> None:
        """Remove a series from the authenticated user's pull list.

        Note: This endpoint requires authentication.

        Args:
            series_pk: The unique identifier of the pull list series entry to remove.

        Raises:
            ApiError: If the entry is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> session.pull_list_remove_series(1)
        """
        self._send_void("DELETE", [ResourceEndpoint.PULL_LIST, "series", series_pk, "remove"])
