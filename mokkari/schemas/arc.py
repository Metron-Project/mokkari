"""
Arc module.

This module provides the following classes:

- Arc
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Arc(BaseResource):
    """
    The Arc object extends :obj:`BaseResource` providing  all information for a story arc.

    Attributes:
        desc (str): The description of the story arc.
        image (HttpUrl): The url for an image associated with the story arc.
        cv_id (int): Comic Vine ID for the story arc.
        resource_url (HttpUrl): The url for the resource.
    """

    desc: str | None = None
    image: HttpUrl | None = None
    cv_id: int | None = None
    resource_url: HttpUrl
