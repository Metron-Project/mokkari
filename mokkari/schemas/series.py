"""
Series module.

This module provides the following classes:

- AssociatedSeries
- CommonSeries
- BaseSeries
- Series
"""

from datetime import datetime

from pydantic import Field, HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.generic import GenericItem


class AssociatedSeries(BaseModel):
    """
    The :obj:`AssociatedSeries` object contains information about an associated series.

    Attributes:
        id (int): The Metron identification number for the associated series.
        name (str): The name of the associated series.
    """

    id: int
    name: str = Field(alias="series")


class CommonSeries(BaseModel):
    """
    The :obj:`CommonSeries` contains fields common to :obj:`BaseSeries` & :obj:`Series` objects.

    Attributes:
        id (int): The Metron identification number for the series.
        year_began (int): The year the series began.
        issue_count (int): The number of issues.
        modified (datetime): The date/time the series was last changed.
    """

    id: int
    year_began: int
    issue_count: int
    modified: datetime


class BaseSeries(CommonSeries):
    """
    The :obj:`BaseSeries` object contains extend the :obj:`CommonSeries`.

    Attributes:
        display_name (str): The name of the series.
    """

    display_name: str = Field(alias="series")


class Series(CommonSeries):
    """
    :obj:`Series` extends :obj:`CommonSeries` and contains all information about a series.

    Attributes:
        name (str): The name of the series.
        sort_name (str): The name used to determine the sort order for a series.
        volume (int): The volume of the series.
        series_type (GenericItem): The type of series.
        publisher (GenericItem): The publisher of the series.
        year_end (int): The year the series ended.
        desc (str): The description of the series.
        genres list(Generic): The genres of the series.
        associated list(AssociatedSeries): The series associated with the series.
        cv_id (int): The Comic Vine ID of the series.
        resource_url (HttpUrl): The URL of the series
    """

    name: str
    sort_name: str
    volume: int
    series_type: GenericItem
    publisher: GenericItem
    year_end: int | None = None
    desc: str | None = None
    genres: list[GenericItem] = []
    associated: list[AssociatedSeries] = []
    cv_id: int | None = None
    resource_url: HttpUrl
