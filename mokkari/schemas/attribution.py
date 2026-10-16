"""Attribution module.

This module provides the following classes:

- Attribution
"""

__all__ = ["Attribution"]

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class Attribution(BaseModel):
    """A data model representing the source of a resource's information.

    Attributes:
        source (str): The name of the source (e.g. "Marvel", "DC", "Wikipedia",
            "Grand Comics Database").
        url (HttpUrl): The URL of the page the information was obtained from.
    """

    source: str
    url: HttpUrl
