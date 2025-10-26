# ruff: noqa: RUF012
"""Issue module.

This module provides the following classes:

- Credit
- CreditPost
- CreditPostResponse
- BasicSeries
- IssueSeries
- CommonIssue
- BaseIssue
- Issue
- IssuePost
- IssuePostResponse
"""

__all__ = [
    "BaseIssue",
    "BasicSeries",
    "CommonIssue",
    "Credit",
    "CreditPost",
    "CreditPostResponse",
    "Issue",
    "IssuePost",
    "IssuePostResponse",
    "IssueSeries",
]

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, HttpUrl, StringConstraints

from mokkari.schemas import BaseModel
from mokkari.schemas.base import BaseResource
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.reprint import Reprint
from mokkari.schemas.variant import Variant


class Credit(BaseModel):
    """A class representing a credit with ID, creator, and role.

    Attributes:
        id (int): The ID of the credit.
        creator (str): The creator associated with the credit.
        role (list[GenericItem]): The role of the credit.
    """

    id: int
    creator: str
    role: list[GenericItem] = []


class CreditPost(BaseModel):
    """A data model representing a credit to be created.

    Attributes:
        issue (int): The ID of the issue.
        creator (int): The ID of the creator.
        role (list[int]): The IDs of the roles.
    """

    issue: int
    creator: int
    role: list[int]


class CreditPostResponse(CreditPost):
    """A data model representing the response after creating a credit.

    Attributes:
        id (int): The ID of the credit.
        issue (int): The ID of the issue.
        creator (int): The ID of the creator.
        role (list[int]): The IDs of the roles.
        modified (datetime): The date and time when the credit was modified.
    """

    id: int
    modified: datetime


class BasicSeries(BaseModel):
    """A class representing a basic series with name, volume, and year began.

    Attributes:
        name (str): The name of the series.
        volume (int): The volume of the series.
        year_began (int): The year the series began.
    """

    name: str
    volume: int
    year_began: int


class IssueSeries(BaseModel):
    """A data model representing an issue series.

    Attributes:
        id (int): The unique identifier of the issue series.
        name (str): The name of the issue series.
        sort_name (str): The name used for sorting the issue series.
        volume (int): The volume number of the issue series.
        year_began (int): The year the issue's series began.
        series_type (GenericItem): The type of the issue series.
        genres (list[GenericItem], optional): The genres associated with the issue series.
    """

    # TODO: Should this have the status field?
    id: int
    name: str
    sort_name: str
    volume: int
    year_began: int
    series_type: GenericItem
    genres: list[GenericItem] = []


class CommonIssue(BaseModel):
    """A data model representing a common issue.

    Attributes:
        id (int): The unique identifier of the common issue.
        number (str): The number of the common issue.
        cover_date (date): The cover date of the common issue.
        store_date (date, optional): The store date of the common issue.
        foc_date (date, optional): The final order cutoff date of the issue.
        image (HttpUrl, optional): The image URL of the common issue.
        cover_hash (str): The hash value of the common issue cover.
        modified (datetime): The date and time when the common issue was last modified.
    """

    id: int
    number: str
    cover_date: date
    store_date: date | None = None
    foc_date: date | None = None
    image: HttpUrl | None = None
    cover_hash: str = ""
    modified: datetime


class BaseIssue(CommonIssue):
    """A data model representing a base issue that extends CommonIssue.

    Attributes:
        issue_name (str): The name of the base issue.
        series (BasicSeries): The basic series associated with the base issue.
    """

    issue_name: str = Field(alias="issue")
    series: BasicSeries


class Issue(CommonIssue):
    """A data model representing an issue that extends CommonIssue.

    Attributes:
        publisher (GenericItem): The publisher of the issue.
        imprint (GenericItem, optional): The imprint of the issue or None.
        series (IssueSeries): The series to which the issue belongs.
        alt_number (str): The alternative number of the issue.
        collection_title (str): The title of the issue collection.
        story_titles (list[str]): The titles of the stories in the issue.
        price (Decimal, optional): The price of the issue.
        price_currency (str): The currency type for the price field.
        rating (GenericItem): The rating of the issue.
        sku (str): The stock keeping unit (SKU) of the issue.
        isbn (str): The International Standard Book Number (ISBN) of the issue.
        upc (str): The Universal Product Code (UPC) of the issue.
        page_count (int, optional): The number of pages in the issue.
        desc (str): The description of the issue.
        arcs (list[BaseResource], optional): The arcs associated with the issue.
        credits (list[Credit], optional): The credits for the issue.
        characters (list[BaseResource], optional): The characters featured in the issue.
        teams (list[BaseResource], optional): The teams involved in the issue.
        universes (list[BaseResource], optional): The universes related to the issue.
        reprints (list[Reprint], optional): The reprints of the issue.
        variants (list[Variant], optional): The variants of the issue.
        cv_id (int, optional): The Comic Vine ID of the issue.
        gcd_id (int, optional): The Grand Comics Database ID of the issue.
        resource_url (HttpUrl): The URL of the issue resource.
    """

    publisher: GenericItem
    imprint: GenericItem | None = None
    series: IssueSeries
    alt_number: str
    collection_title: str = Field(alias="title")
    story_titles: list[str] = Field(alias="name")
    price: Decimal | None = None
    price_currency: str
    rating: GenericItem
    sku: str
    isbn: str
    upc: str
    page_count: int | None = Field(alias="page", default=None)
    desc: str
    arcs: list[BaseResource] = []
    credits: list[Credit] = []
    characters: list[BaseResource] = []
    teams: list[BaseResource] = []
    universes: list[BaseResource] = []
    reprints: list[Reprint] = []
    variants: list[Variant] = []
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl


class IssuePost(BaseModel):
    """A data model representing an issue to be created.

    Attributes:
        series (int, optional): The ID of the series to which the issue belongs.
        number (str, optional): The number of the issue.
        alt_number (str, optional): The alternative number of the issue.
        title (str, optional): The collection title of the issue.
        name (list[str], optional): The story titles of the issue.
        cover_date (date, optional): The cover date of the issue.
        store_date (date, optional): The store date of the issue.
        foc_date (date, optional): The final order cutoff date of the issue.
        price (Decimal, optional): The price of the issue.
        rating (int, optional): The ID of the rating of the issue.
        sku (str, optional): The SKU of the issue.
        isbn (str, optional): The ISBN of the issue.
        upc (str, optional): The UPC of the issue.
        page (int, optional): The number of pages in the issue.
        desc (str, optional): The description of the issue.
        image (str, optional): The image URL of the issue.
        arcs (list[int], optional): The IDs of the arcs associated with the issue.
        characters (list[int], optional): The IDs of the characters featured in the issue.
        teams (list[int], optional): The IDs of the teams involved in the issue.
        universes (list[int], optional): The IDs of the universes related to the issue.
        reprints (list[int], optional): The IDs of the reprints of the issue.
        cv_id (int, optional): The Comic Vine ID of the issue.
        gcd_id (int, optional): The Grand Comics Database ID of the issue.
    """

    series: int | None = None
    number: Annotated[str, StringConstraints(max_length=25)] | None = None
    alt_number: Annotated[str, StringConstraints(max_length=25)] | None = None
    title: str | None = None  # Collection Title
    name: list[Annotated[str, StringConstraints(max_length=150)]] | None = None
    cover_date: date | None = None
    store_date: date | None = None
    foc_date: date | None = None
    price: Decimal | None = None
    rating: int | None = None
    sku: Annotated[str, StringConstraints(max_length=12)] | None = None
    isbn: Annotated[str, StringConstraints(max_length=13)] | None = None
    upc: Annotated[str, StringConstraints(max_length=20)] | None = None
    page: int | None = None
    desc: str | None = None
    image: str | None = None
    arcs: list[int] | None = None
    characters: list[int] | None = None
    teams: list[int] | None = None
    universes: list[int] | None = None
    reprints: list[int] | None = None
    cv_id: int | None = None
    gcd_id: int | None = None


class IssuePostResponse(IssuePost):
    """A data model representing the response from creating an issue.

    Attributes:
        id: The ID of the issue.
        series (int, optional): The ID of the series to which the issue belongs.
        number (str, optional): The number of the issue.
        alt_number (str, optional): The alternative number of the issue.
        title (str, optional): The collection title of the issue.
        name (list[str], optional): The story titles of the issue.
        cover_date (date, optional): The cover date of the issue.
        store_date (date, optional): The store date of the issue.
        foc_date (date, optional): The final order cutoff date of the issue.
        price (Decimal, optional): The price of the issue.
        rating (int, optional): The ID of the rating of the issue.
        sku (str, optional): The SKU of the issue.
        isbn (str, optional): The ISBN of the issue.
        upc (str, optional): The UPC of the issue.
        page (int, optional): The number of pages in the issue.
        desc (str, optional): The description of the issue.
        image (str, optional): The image URL of the issue.
        arcs (list[int], optional): The IDs of the arcs associated with the issue.
        characters (list[int], optional): The IDs of the characters featured in the issue.
        teams (list[int], optional): The IDs of the teams involved in the issue.
        universes (list[int], optional): The IDs of the universes related to the issue.
        reprints (list[int], optional): The IDs of the reprints of the issue.
        cv_id (int, optional): The Comic Vine ID of the issue.
        gcd_id (int, optional): The Grand Comics Database ID of the issue.
        resource_url (HttpUrl): The URL of the issue resource.
    """

    # TODO: For some reason the Issue POST & PATCH responses don't include the modified field, should fix that.
    id: int
    resource_url: HttpUrl
