# ruff: noqa: RUF012
"""Issue module.

This module provides the following classes:

- Credit
- BasicSeries
- IssueSeries
- CommonIssue
- BaseIssue
- Issue
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, HttpUrl

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
        image (HttpUrl, optional): The image URL of the common issue.
        cover_hash (str): The hash value of the common issue cover.
        modified (datetime): The date and time when the common issue was last modified.
    """

    id: int
    number: str
    cover_date: date
    store_date: date | None = None
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
        collection_title (str): The title of the issue collection.
        story_titles (list[str]): The titles of the stories in the issue.
        price (Decimal, optional): The price of the issue.
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
    collection_title: str = Field(alias="title")
    story_titles: list[str] = Field(alias="name")
    price: Decimal | None = None
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
