"""Generic module.

This module provides the following classes:

- GenericItem
"""

from mokkari.schemas import BaseModel


class GenericItem(BaseModel):
    """A data model representing a generic item.

    Attributes:
        id (int): The unique identifier of the generic item.
        name (str): The name of the generic item.
    """

    id: int
    name: str
