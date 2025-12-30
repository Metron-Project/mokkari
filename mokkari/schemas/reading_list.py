"""Reading List module.

This module provides the following classes:

- AttributionSource
- ReadingListIssue
- ReadingListItem
- ReadingListList
- ReadingListRead
"""

__all__ = [
    "AttributionSource",
    "ReadingListIssue",
    "ReadingListItem",
    "ReadingListList",
    "ReadingListRead",
]

from datetime import date, datetime
from enum import Enum

from pydantic import Field, HttpUrl, field_validator

from mokkari.schemas import BaseModel
from mokkari.schemas.issue import BasicSeries
from mokkari.schemas.user import User


class AttributionSource(str, Enum):
    """Enumeration of attribution sources for reading lists.

    Values:

        CBRO: Comic Book Reading Orders
        CMRO: Complete Marvel Reading Orders
        CBH: Comic Book Herald
        CBT: Comic Book Treasury
        MG: Marvel Guides
        HTLC: How To Love Comics
        LOCG: League of ComicGeeks
        OTHER: Other sources
    """

    CBRO = "CBRO"
    CMRO = "CMRO"
    CBH = "CBH"
    CBT = "CBT"
    MG = "MG"
    HTLC = "HTLC"
    LOCG = "LOCG"
    OTHER = "OTHER"


class ReadingListIssue(BaseModel):
    """A data model representing an issue in a reading list (without image and cover_hash).

    Attributes:
        id (int): The unique identifier of the issue.
        series (BasicSeries): The series associated with the issue.
        number (str): The number of the issue.
        cover_date (date): The cover date of the issue.
        store_date (date, optional): The store date of the issue.
        cv_id (int, optional): The Comic Vine ID of the issue.
        gcd_id (int, optional): The Grand Comics Database ID of the issue.
        modified (datetime): The date and time when the issue was last modified.
    """

    id: int
    series: BasicSeries
    number: str
    cover_date: date
    store_date: date | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    modified: datetime


class ReadingListItem(BaseModel):
    """A data model representing an item in a reading list.

    Attributes:
        id (int): The unique identifier of the reading list item.
        issue (ReadingListIssue): The issue associated with this reading list item.
        order (int, optional): Position of this issue in the reading list.
        issue_type (str): The type of the issue.
    """

    id: int
    issue: ReadingListIssue
    order: int | None = None
    issue_type: str


class ReadingListList(BaseModel):
    """A data model representing a reading list in list view.

    Attributes:
        id (int): The unique identifier of the reading list.
        name (str): The name of the reading list.
        slug (str): The slug for the reading list.
        user (User): The user who owns the reading list.
        is_private (bool): Whether this list is private (only visible to the owner).
        attribution_source (AttributionSource, optional): Source where this reading list
            information was obtained.
        average_rating (float, optional): The average rating of the reading list.
        rating_count (int): The number of ratings for the reading list.
        modified (datetime): The date and time when the reading list was last modified.
    """

    id: int
    name: str
    slug: str
    user: User
    is_private: bool = False
    attribution_source: AttributionSource | None = None
    average_rating: float | None = None
    rating_count: int
    modified: datetime

    @field_validator("attribution_source", mode="before")
    @classmethod
    def convert_empty_string_to_none(_cls, v: str | None) -> str | None:  # noqa: N804
        """Convert empty strings to None for attribution_source.

        The API may return an empty string when there is no attribution source,
        but we want to store this as None internally.

        Args:
            v: The value to validate

        Returns:
            None if the value is an empty string, otherwise the original value
        """
        if v == "":
            return None
        return v


class ReadingListRead(BaseModel):
    """A data model representing a reading list in detailed view.

    Attributes:
        id (int): The unique identifier of the reading list.
        user (User): The user who owns the reading list.
        name (str): The name of the reading list.
        slug (str): The slug for the reading list.
        desc (str): The description of the reading list.
        is_private (bool): Whether this list is private (only visible to the owner).
        attribution_source (str): Source where this reading list information was obtained.
        attribution_url (HttpUrl, optional): URL of the specific page where this reading
            list was obtained.
        average_rating (float): The average rating of the reading list.
        rating_count (int): The number of ratings for the reading list.
        items_url (str): URL to the paginated items endpoint.
        resource_url (str): URL of the reading list resource.
        modified (datetime): The date and time when the reading list was last modified.
    """

    id: int
    user: User
    name: str
    slug: str
    desc: str = ""
    is_private: bool = False
    attribution_source: str
    attribution_url: HttpUrl | None = Field(default=None, max_length=200)
    average_rating: float | None = None
    rating_count: int
    items_url: str
    resource_url: str
    modified: datetime
