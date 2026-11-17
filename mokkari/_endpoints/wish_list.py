"""Wish list endpoints for ``Session``.

This module provides the following class:

- WishListEndpoints: The authenticated user's wish list.
"""

from __future__ import annotations

__all__ = ["WishListEndpoints"]

from typing import TYPE_CHECKING

from mokkari.cache import ResourceEndpoint
from mokkari.schemas.wish_list import (
    AcquireWishListItem,
    WishList,
    WishListAddItem,
    WishListItemList,
    WishListItemRead,
)

if TYPE_CHECKING:
    from mokkari._endpoints._helpers import EndpointHelpers as _Base
else:
    _Base = object


class WishListEndpoints(_Base):
    """The authenticated user's wish list methods of ``Session``.

    A mixin: it relies on the request, cache and validation helpers of ``Session``
    (see ``EndpointHelpers``).
    """

    # Wish list methods
    def wish_list(self) -> WishList:
        """Retrieve the authenticated user's wish list.

        Note: This endpoint requires authentication.

        Returns:
            A WishList object.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> wl = session.wish_list()
            >>> print(f"Items: {wl.item_count}")
        """
        results = self._list_resources(ResourceEndpoint.WISH_LIST, None, WishList)
        return results[0]

    def wish_list_items(self, params: dict[str, str | int] | None = None) -> list[WishListItemList]:
        """Retrieve wish list items for the authenticated user.

        Note: This endpoint requires authentication.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[WishListItemList]: A list of WishListItemList objects.

        Raises:
            ApiError: If there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> items = session.wish_list_items()
            >>> for item in items:
            ...     print(f"{item.issue.series.name} #{item.issue.number} - {item.status}")
        """
        resp = self._get_results([ResourceEndpoint.WISH_LIST, "items"], params)
        return self._validate_list_response(resp, WishListItemList)

    def wish_list_add_item(self, data: WishListAddItem) -> WishListItemRead:
        """Add an issue to the authenticated user's wish list.

        Note: This endpoint requires authentication.

        Args:
            data: WishListAddItem object containing the issue_id and optional fields.

        Returns:
            WishListItemRead: The newly created wish list item.

        Raises:
            ApiError: If the issue is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> from mokkari.schemas.wish_list import WishListAddItem
            >>> item = session.wish_list_add_item(WishListAddItem(issue_id=1, priority=2))
            >>> print(f"Added: {item.issue.series.name} #{item.issue.number}")
        """
        return self._handle_write_request(
            "POST", [ResourceEndpoint.WISH_LIST, "items", "add"], data, WishListItemRead
        )

    def wish_list_acquire_item(self, item_pk: int, data: AcquireWishListItem) -> None:
        """Mark a wish list item as acquired and create a collection item.

        Note: This endpoint requires authentication.

        Args:
            item_pk: The unique identifier of the wish list item to acquire.
            data: AcquireWishListItem object with optional purchase details.

        Raises:
            ApiError: If the item is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> from mokkari.schemas.wish_list import AcquireWishListItem
            >>> session.wish_list_acquire_item(1, AcquireWishListItem(purchase_price="9.99"))
        """
        # Acquiring the item adds it to the collection.
        self._send_void(
            "POST",
            [ResourceEndpoint.WISH_LIST, "items", item_pk, "acquire"],
            data,
            also_invalidates=(ResourceEndpoint.COLLECTION,),
        )

    def wish_list_remove_item(self, item_pk: int) -> None:
        """Remove an item from the authenticated user's wish list.

        Note: This endpoint requires authentication.

        Args:
            item_pk: The unique identifier of the wish list item to remove.

        Raises:
            ApiError: If the item is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> session.wish_list_remove_item(1)
        """
        self._send_void("DELETE", [ResourceEndpoint.WISH_LIST, "items", item_pk, "remove"])
