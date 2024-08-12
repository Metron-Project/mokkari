"""Imprint module.

This module provides the following classes:

- Imprint
"""

from mokkari.schemas.generic import GenericItem
from mokkari.schemas.publisher import Publisher


class Imprint(Publisher):
    """A data model representing an imprint that extends Publisher.

    Attributes:
        publisher (GenericItem): The generic item representing the publisher.

    """

    publisher: GenericItem
