"""Publisher module.

This module provides the following classes:

- Publisher
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Publisher(BaseResource):
    """A data model representing a publisher that extends BaseResource.

    Attributes:
        founded (int, optional): The year the publisher was founded.
        desc (str): The description of the publisher.
        image (HttpUrl, optional): The image URL of the publisher.
        cv_id (int, optional): The Comic Vine ID of the publisher.
        gcd_id (int, optional): The Grand Comics Database ID of the publisher.
        resource_url (HttpUrl): The URL of the publisher resource.
    """

    founded: int | None = None
    desc: str
    image: HttpUrl | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl
