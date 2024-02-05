"""
Base module.

This module provides the following classes:

- BaseResource
"""

from datetime import datetime

from mokkari.schemas import BaseModel


class BaseResource(BaseModel):
    """
    The :obj:`BaseResource` object contains a list of items for a resource.

    Attributes:
        id (int): The Metron identification number for the resource.
        name (str): The name of the resource.
        modified (datetime): The date/time the resource was last changed.
    """

    id: int
    name: str
    modified: datetime
