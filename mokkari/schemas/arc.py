"""Arc module.

This module provides the following classes:

- Arc
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Arc(BaseResource):
    """A data model representing an arc that extends BaseResource.

    Attributes:
        desc (str): The description of the arc.
        image (HttpUrl, optional): The image URL of the arc.
        cv_id (int, optional): The Comic Vine ID of the arc.
        gcd_id (int, optional): The Grand Comics Database ID of the arc.
        resource_url (HttpUrl): The URL of the arc resource.
    """

    desc: str
    image: HttpUrl | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl
