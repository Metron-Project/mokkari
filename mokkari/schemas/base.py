"""Base module.

This module provides the following classes:

- BaseResource
"""

from datetime import datetime

from mokkari.schemas import BaseModel


class BaseResource(BaseModel):
    """A data model representing a base resource.

    Attributes:
        id (int): The unique identifier of the base resource.
        name (str): The name of the base resource.
        modified (datetime): The date and time when the base resource was last modified.
    """

    id: int
    name: str
    modified: datetime
