"""Wish list module.

This module provides the following classes:

- Currency
- Priority
- WishList
- WishListItemList
- WishListItemRead
- WishListAddItem
- AcquireWishListItem
"""

__all__ = [
    "AcquireWishListItem",
    "Currency",
    "Priority",
    "WishList",
    "WishListAddItem",
    "WishListItemList",
    "WishListItemRead",
]

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from mokkari.schemas import BaseModel
from mokkari.schemas.collection import CollectionIssue, Grade


class Priority(int, Enum):
    """Enumeration of wish list item priority levels (1=highest, 5=lowest).

    Values:

        ONE: Priority 1 (highest)
        TWO: Priority 2
        THREE: Priority 3 (default)
        FOUR: Priority 4
        FIVE: Priority 5 (lowest)
    """

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class Currency(str, Enum):
    """Enumeration of supported currencies.

    Values:

        USD: US Dollar
        GBP: British Pound Sterling
    """

    USD = "USD"
    GBP = "GBP"


class WishList(BaseModel):
    """A data model representing a user's wish list.

    Attributes:
        id (int): The unique identifier of the wish list.
        item_count (int): Number of items in the wish list.
        items_url (str): URL to retrieve the wish list items.
        modified (datetime): The date and time when the wish list was last modified.
    """

    id: int
    item_count: int
    items_url: str
    modified: datetime


class WishListItemList(BaseModel):
    """A data model representing a wish list item in list view.

    Attributes:
        id (int): The unique identifier of the wish list item.
        issue (CollectionIssue): The issue associated with this wish list item.
        status (str): The current status of the wish list item.
        priority (Priority, optional): The priority level for acquiring this item.
        desired_grade (Grade, optional): The desired CGC grade for the issue.
        modified (datetime): The date and time when the item was last modified.
    """

    id: int
    issue: CollectionIssue
    status: str
    priority: Priority | None = None
    desired_grade: Grade | None = None
    modified: datetime


class WishListItemRead(BaseModel):
    """A data model representing a wish list item in detailed view.

    Attributes:
        id (int): The unique identifier of the wish list item.
        issue (CollectionIssue): The issue associated with this wish list item.
        status (str): The current status of the wish list item.
        priority (Priority, optional): The priority level for acquiring this item.
        desired_grade (Grade, optional): The desired CGC grade for the issue.
        max_price (Decimal, optional): The maximum price willing to pay.
        max_price_currency (str, optional): Currency code for max_price (e.g. "USD", "GBP").
        notes (str): Additional notes about this wish list item.
        added_on (datetime): The date and time when the item was added to the wish list.
        modified (datetime): The date and time when the item was last modified.
    """

    id: int
    issue: CollectionIssue
    status: str
    priority: Priority | None = None
    desired_grade: Grade | None = None
    max_price: Decimal | None = None
    max_price_currency: str | None = None
    notes: str = ""
    added_on: datetime
    modified: datetime


class WishListAddItem(BaseModel):
    """A data model representing a request to add an issue to the wish list.

    Attributes:
        issue_id (int): The unique identifier of the issue to add.
        priority (int): Priority level 1-5 (default 3).
        desired_grade (Decimal, optional): The desired CGC grade for the issue.
        max_price (Decimal, optional): The maximum price willing to pay.
        max_price_currency (str): Currency for max_price (default "USD").
        notes (str): Additional notes about this wish list item.
    """

    issue_id: int
    priority: int = Field(default=3, ge=1, le=5)
    desired_grade: Decimal | None = None
    max_price: Decimal | None = None
    max_price_currency: str = "USD"
    notes: str = ""


class AcquireWishListItem(BaseModel):
    """A data model representing a request to mark a wish list item as acquired.

    This creates a new collection item from the wish list item.

    Attributes:
        purchase_date (date, optional): The date the issue was purchased.
        purchase_price (Decimal, optional): The price paid for the issue.
        purchase_price_currency (str): Currency for purchase_price (default "USD").
        purchase_store (str): The store or vendor where the issue was purchased.
        notes (str): Additional notes about the purchase.
    """

    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    purchase_price_currency: str = "USD"
    purchase_store: str = ""
    notes: str = ""
