"""
Publisher module.

This module provides the following classes:

- BasePublisher
- Publisher
"""

from datetime import datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class BasePublisher(BaseModel):
    """
    The :obj:`BasePublisher` object contains a list of publishers.

    Attributes:
        id (int): The Metron identification number for the publisher.
        name (str): The name of the publisher.
        modified (datetime): The date/time the team was last changed.
    """

    id: int
    name: str
    modified: datetime


class Publisher(BasePublisher):
    """
    The Publisher object extends :obj:`BasePublisher` providing  all information for a publisher.

    Attributes:
        founded (int): The year the publisher was founded.
        desc (str): The description of the publisher.
        image (HttpUrl): The url for an image associated with the publisher.
        cv_id (int): Comic Vine ID for the publisher.
        resource_url (HttpUrl): The url for the resource.
    """

    founded: int | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    cv_id: int | None = None
    resource_url: HttpUrl
