"""
PublishersList module.

This module provides the following classes:

- PublishersList
"""
from marshmallow import ValidationError

from mokkari import exceptions, publisher


class PublishersList:
    """The PublishersList object contains a list of `Publisher` objects."""

    def __init__(self, response):
        """Initialize a new PublishersList."""
        self.publishers = []

        schema = publisher.PublisherSchema()
        for pub_dict in response["results"]:
            try:
                result = schema.load(pub_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.publishers.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.publishers)

    def __len__(self):
        """Return the length of the object."""
        return len(self.publishers)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.publishers[index]
