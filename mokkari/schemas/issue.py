"""
Issue module.

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
from mokkari.schemas.arc import BaseArc
from mokkari.schemas.character import BaseCharacter
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.reprint import Reprint
from mokkari.schemas.team import BaseTeam
from mokkari.schemas.universe import BaseUniverse
from mokkari.schemas.variant import Variant


class Credit(BaseModel):
    """
    The :obj:`Credit` object contains information about an issue creator credits.

    Attributes:
        id (int): The Metron identification number for the issue credit.
        creator (str): The name of the creator for the issue credit.
        role (list[GenericItem]): The role of the creator for the issue.
    """

    id: int
    creator: str
    role: list[GenericItem] = []


class BasicSeries(BaseModel):
    """
    The :obj:`BasicSeries` object contains basic series information for an issue.

    Attributes:
        name (str): The name of the series.
        volume (int): The volume of the series.
        year_began (int): The year the series began.
    """

    name: str
    volume: int
    year_began: int


class IssueSeries(BaseModel):
    """
    The :obj:`AssociatedSeries` object contains more detailed series information.

    Attributes:
        id (int): The Metron identification number for series.
        name (str): The name of the series.
        sort_name (str): The sort name of the series.
        volume (int): The volume of the series.
        series_type (GenericItem): The type of series.
        genres (list[Generic]): The genres of the series.
    """

    id: int
    name: str
    sort_name: str
    volume: int
    series_type: GenericItem
    genres: list[GenericItem] = []


class CommonIssue(BaseModel):
    """
    The :obj:`CommonIssue` object contains common information for BaseIssue and Issue objects.

    Attributes:
        id (int): The Metron identification number for the associated series.
        number (str): The number of the issue.
        cover_date (date): The cover date of the issue.
        image (HttpUrl): The url of the cover image for the issue.
        cover_hash (str): The hash of the cover image for the issue.
        modified (datetime): The modified date of the issue.
    """

    id: int
    number: str
    cover_date: date
    image: HttpUrl | None = None
    cover_hash: str | None = None
    modified: datetime


class BaseIssue(CommonIssue):
    """
    The :obj:`BaseIssue` object extends the :obj:`CommonIssue` object.

    Attributes:
        issue_name (str): The name of the issue.
        series (BasicSeries): The series for the issue.
    """

    issue_name: str = Field(alias="issue")
    series: BasicSeries


class Issue(CommonIssue):
    """
    The :obj:`Issue` object extends the :obj:`CommonIssue` object with all the info for an issue.

    Attributes:
        publisher (GenericPublisher): The publisher of the issue.
        series (IssueSeries): The series for the issue.
        collection_title (str): The collection title of the issue. Normally only used with TPB.
        story_titles (list[str]): A list of stories contained in the issue.
        cover_date (date): The cover date of the issue.
        store_date (date): The store date of the issue.
        price (Decimal): The price of the issue.
        rating (GenericItem): The rating of the issue.
        sku (str): The sku of the issue.
        isbn (str): The isbn of the issue.
        upc (str): The upc of the issue.
        page_count (int): The number of pages of the issue.
        desc (str): The description of the issue.
        arcs (list[BaseArc]): A list of story arcs for the issue.
        credits (list[Credit]): A list of creator credits for the issue.
        characters (list[BaseCharacter]): A list of characters for the issue.
        teams (list[BaseTeam]): A list of teams for the issue.
        reprints (list[Reprint]): A list of issues printed,
        variants (list[Variant]): A list of variant covers for the issue.
        cv_id (int): The Comic Vine ID of the issue.
        resource_url (HttpUrl): The URL of the issue.
    """

    publisher: GenericItem
    series: IssueSeries
    collection_title: str = Field(alias="title")
    story_titles: list[str] = Field(alias="name")
    cover_date: date
    store_date: date | None = None
    price: Decimal | None = None
    rating: GenericItem
    sku: str | None = None
    isbn: str | None = None
    upc: str | None = None
    page_count: int | None = Field(alias="page", default=None)
    desc: str | None = None
    arcs: list[BaseArc] = []
    credits: list[Credit] = []
    characters: list[BaseCharacter] = []
    teams: list[BaseTeam] = []
    universes: list[BaseUniverse] = []
    reprints: list[Reprint] = []
    variants: list[Variant] = []
    cv_id: int | None = None
    resource_url: HttpUrl
