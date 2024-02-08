"""
Publisher module.

This module provides the following classes:

- Publisher
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Publisher(BaseResource):
    """
    The Publisher object extends :obj:`BaseResource` providing  all information for a publisher.

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
