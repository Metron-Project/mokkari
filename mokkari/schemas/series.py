# ruff: noqa: RUF012
"""Series module.

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
    """A data model representing an associated series.

    Attributes:
        id (int): The unique identifier of the associated series.
        name (str): The name of the associated series.
    """

    id: int
    name: str = Field(alias="series")


class CommonSeries(BaseModel):
    """A data model representing a common series.

    Attributes:
        id (int): The unique identifier of the common series.
        year_began (int): The year the common series began.
        issue_count (int): The number of issues in the common series.
        volume (int): The volume number of the common series.
        modified (datetime): The date and time when the common series was last modified.
    """

    id: int
    year_began: int
    issue_count: int
    volume: int
    modified: datetime


class BaseSeries(CommonSeries):
    """A data model representing a base series that extends CommonSeries.

    Attributes:
        display_name (str): The display name of the base series.
    """

    display_name: str = Field(alias="series")


class Series(CommonSeries):
    """A data model representing a series that extends CommonSeries.

    Attributes:
        name (str): The name of the series.
        sort_name (str): The name used for sorting the series.
        series_type (GenericItem): The type of the series.
        status (str): The status of the series.
        publisher (GenericItem): The publisher of the series.
        imprint (GenericItem, optional): The imprint of the series or None.
        year_end (int, optional): The year the series ended.
        desc (str): The description of the series.
        genres (list[GenericItem], optional): The genres associated with the series.
        associated (list[AssociatedSeries], optional): The associated series.
        cv_id (int, optional): The Comic Vine ID of the series.
        gcd_id (int, optional): The Grand Comics Database ID of the series.
        resource_url (HttpUrl): The URL of the series resource.
    """

    name: str
    sort_name: str
    series_type: GenericItem
    status: str
    publisher: GenericItem
    imprint: GenericItem | None = None
    year_end: int | None = None
    desc: str
    genres: list[GenericItem] = []
    associated: list[AssociatedSeries] = []
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl
