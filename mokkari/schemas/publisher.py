"""Publisher module.

This module provides the following classes:

- Publisher
"""

__all__ = ["Publisher", "PublisherPost"]

from typing import Annotated

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.base import BaseResource

COUNTY_CODE_LENGTH = 2


def ensure_country_code_length(value: str) -> str:
    """Ensure the country length is correct."""
    # Should verify it's a valid country code, but checking its length should suffice for now.
    if not value:
        return value
    if len(value) != COUNTY_CODE_LENGTH:
        msg = f"Country code must be {COUNTY_CODE_LENGTH} characters long."
        raise ValueError(msg)
    return value


class Publisher(BaseResource):
    """A data model representing a publisher that extends BaseResource.

    Attributes:
        founded (int, optional): The year the publisher was founded.
        country: str: An ISO 3166-1 2-letter country code.
        desc (str): The description of the publisher.
        image (HttpUrl, optional): The image URL of the publisher.
        cv_id (int, optional): The Comic Vine ID of the publisher.
        gcd_id (int, optional): The Grand Comics Database ID of the publisher.
        resource_url (HttpUrl): The URL of the publisher resource.
    """

    founded: int | None = None
    country: Annotated[str, ensure_country_code_length]
    desc: str
    image: HttpUrl | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl


class PublisherPost(BaseModel):
    """A data model representing a publisher to be created.

    Attributes:
        name (str, optional): The name of the publisher.
        founded (int, optional): The year the publisher was founded.
        country: str: An ISO 3166-1 2-letter country code. Defaults to 'US'.
        desc (str, optional): The description of the publisher.
        image (str, optional): The image URL of the publisher.
        cv_id (int, optional): The Comic Vine ID of the publisher.
        gcd_id (int, optional): The Grand Comics Database ID of the publisher.
    """

    name: str | None = None
    founded: int | None = None
    country: Annotated[str, ensure_country_code_length] = "US"
    desc: str | None = None
    image: str | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
