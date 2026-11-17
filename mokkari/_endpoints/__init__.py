"""The public endpoint methods of ``Session``, grouped by domain into mixins.

This private package provides the following classes:

- CatalogEndpoints: Creators, characters, publishers, teams, arcs, series, issues,
  universes and imprints
- ReadingListEndpoints: Reading lists and their items
- CollectionEndpoints: The authenticated user's collection
- PullListEndpoints: The authenticated user's pull list
- WishListEndpoints: The authenticated user's wish list
"""

__all__ = [
    "CatalogEndpoints",
    "CollectionEndpoints",
    "PullListEndpoints",
    "ReadingListEndpoints",
    "WishListEndpoints",
]

from mokkari._endpoints.catalog import CatalogEndpoints
from mokkari._endpoints.collection import CollectionEndpoints
from mokkari._endpoints.pull_list import PullListEndpoints
from mokkari._endpoints.reading_list import ReadingListEndpoints
from mokkari._endpoints.wish_list import WishListEndpoints
