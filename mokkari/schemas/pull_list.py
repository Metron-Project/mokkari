"""Pull list module.

This module provides the following classes:

- PullListRead
- PullListIssue
- PullListSeries
"""

__all__ = [
    "PullListIssue",
    "PullListRead",
    "PullListSeries",
]

from datetime import date, datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.issue import BasicSeries
from mokkari.schemas.series import BaseSeries


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
        series (BaseSeries): The series details.
        added_on (datetime): The date and time when the series was added to the pull list.
    """

    id: int
    series: BaseSeries
    added_on: datetime
