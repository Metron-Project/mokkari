# ruff: noqa: RUF012
"""Series module.

This module provides the following classes:

- AssociatedSeries
- CommonSeries
- BaseSeries
- Series
- SeriesPost
- SeriesPostResponse
"""

__all__ = [
    "AssociatedSeries",
    "BaseSeries",
    "CommonSeries",
    "Series",
    "SeriesPost",
    "SeriesPostResponse",
]

from datetime import datetime

from pydantic import Field, HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.base import BaseResource
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


class SeriesPost(BaseModel):
    """A data model representing a series to be created.

    Attributes:
        name (str, optional): The name of the series.
        sort_name (str, optional): The name used for sorting the series.
        volume (int, optional): The volume number of the series.
        series_type (int, optional): The ID of the series type.
        status (int, optional): The ID of the series status.
        publisher (int, optional): The ID of the publisher of the series.
        imprint (int, optional): The ID of the imprint of the series.
        year_began (int, optional): The year the series began.
        year_end (int, optional): The year the series ended.
        desc (str, optional): The description of the series.
        genres (list[int], optional): The IDs of the genres associated with the series.
        associated (list[int], optional): The IDs of the associated series.
        cv_id (int, optional): The Comic Vine ID of the series.
        gcd_id (int, optional): The Grand Comics Database ID of the series.
    """

    name: str | None = None
    sort_name: str | None = None
    volume: int | None = None
    series_type: int | None = None
    status: int | None = None
    publisher: int | None = None
    imprint: int | None = None
    year_began: int | None = None
    year_end: int | None = None
    desc: str | None = None
    genres: list[int] | None = None
    associated: list[int] | None = None
    cv_id: int | None = None
    gcd_id: int | None = None


class SeriesPostResponse(BaseResource, SeriesPost):
    """A data model representing the response from creating a series.

    Attributes:
        id (int): The unique identifier of the series.
        name (str, optional): The name of the series.
        sort_name (str, optional): The name used for sorting the series.
        volume (int, optional): The volume number of the series.
        series_type (int, optional): The ID of the series type.
        status (int, optional): The ID of the series status.
        publisher (int, optional): The ID of the publisher of the series.
        imprint (int, optional): The ID of the imprint of the series.
        year_began (int, optional): The year the series began.
        year_end (int, optional): The year the series ended.
        desc (str, optional): The description of the series.
        genres (list[int], optional): The IDs of the genres associated with the series.
        associated (list[int], optional): The IDs of the associated series.
        cv_id (int, optional): The Comic Vine ID of the series.
        gcd_id (int, optional): The Grand Comics Database ID of the series.
        resource_url (HttpUrl): The URL of the series resource.
    """
