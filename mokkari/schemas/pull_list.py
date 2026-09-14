"""Pull list module.

This module provides the following classes:

- PullListAddSeries
- PullListIssue
- PullListRead
- PullListSeries
- PullListSeriesDetail
"""

__all__ = [
    "PullListAddSeries",
    "PullListIssue",
    "PullListRead",
    "PullListSeries",
    "PullListSeriesDetail",
]

from datetime import date, datetime

from pydantic import Field, HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.issue import BasicSeries


class PullListAddSeries(BaseModel):
    """A data model representing a request to add a series to the pull list.

    Attributes:
        series_id (int): The unique identifier of the series to add.
    """

    series_id: int


class PullListSeriesDetail(BaseModel):
    """A data model representing series details within a pull list entry.

    Attributes:
        id (int): The unique identifier of the series.
        name (str): The name of the series.
        year_began (int): The year the series began.
        year_end (int, optional): The year the series ended.
        volume (int): The volume number of the series.
        modified (datetime): The date and time when the series was last modified.
    """

    id: int
    name: str = Field(alias="series")
    year_began: int
    year_end: int | None = None
    volume: int
    modified: datetime


class PullListRead(BaseModel):
    """A data model representing a user's pull list.

    Attributes:
        id (int): The unique identifier of the pull list.
        series_count (int): Number of series on the pull list.
        series_url (str): URL to retrieve the pull list series.
        modified (datetime): The date and time when the pull list was last modified.
    """

    id: int
    series_count: int
    series_url: str
    modified: datetime


class PullListIssue(BaseModel):
    """A data model representing an issue on the pull list.

    Attributes:
        id (int): The unique identifier of the issue.
        series (BasicSeries): The series associated with the issue.
        number (str): The issue number.
        issue (str): The full issue name/display string.
        cover_date (date): The cover date of the issue.
        store_date (date, optional): The in-store date of the issue.
        image (HttpUrl, optional): The cover image URL.
        modified (datetime): The date and time when the issue was last modified.
    """

    id: int
    series: BasicSeries
    number: str
    issue: str
    cover_date: date
    store_date: date | None = None
    image: HttpUrl | None = None
    modified: datetime


class PullListSeries(BaseModel):
    """A data model representing a series on the pull list.

    Attributes:
        id (int): The unique identifier of the pull list series entry.
        series (PullListSeriesDetail): The series details.
        added_on (datetime): The date and time when the series was added to the pull list.
    """

    id: int
    series: PullListSeriesDetail
    added_on: datetime
