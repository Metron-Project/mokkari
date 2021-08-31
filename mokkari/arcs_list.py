"""
ArcsList module.

This module provides the following classes:

- ArcsList
"""
from marshmallow import ValidationError

from mokkari import arc, exceptions


class ArcsList:
    """The ArcsList object contains a list of `Arc` objects."""

    def __init__(self, response):
        """Initialize a new ArcsList."""
        self.arcs = []

        schema = arc.ArcSchema()
        for arc_dict in response["results"]:
            try:
                result = schema.load(arc_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.arcs.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.arcs)

    def __len__(self):
        """Return the length of the object."""
        return len(self.arcs)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.arcs[index]
