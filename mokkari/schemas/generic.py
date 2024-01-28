"""
Generic module.

This module provides the following classes:

- GenericItem
"""

from mokkari.schemas import BaseModel


class GenericItem(BaseModel):
    """
    The :obj:`GenericItem` object contains basic information for various resources.

    Attributes:
        id (int): The id of the item.
        name (str): The name of the item.
    """

    id: int
    name: str
