"""
CreatorsList module.

This module provides the following classes:

- CreatorsList
"""
from marshmallow import ValidationError

from mokkari import creator, exceptions


class CreatorsList:
    """The CreatorsList object contains a list of `Creator` objects."""

    def __init__(self, response) -> None:
        """Initialize a new CreatorsList."""
        self.creators = []

        schema = creator.CreatorSchema()
        for creator_dict in response["results"]:
            try:
                result = schema.load(creator_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.creators.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.creators)

    def __len__(self):
        """Return the length of the object."""
        return len(self.creators)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.creators[index]
