"""
Arc module.

This module provides the following classes:

- Arc
- BaseArc
"""

from datetime import datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class BaseArc(BaseModel):
    """
    The :obj:`BaseArc` object contains a list of story arcs.

    Attributes:
        id (int): The Metron identification number for the story arc.
        name (str): The name of the story arc.
        modified (datetime): The date/time the story arc was last changed.
    """

    id: int
    name: str
    modified: datetime


class Arc(BaseArc):
    """
    The Arc object extends :obj:`BaseArc` providing  all information for a story arc.

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
