"""
CharactersList module.

This module provides the following classes:

- CharactersList
"""
from marshmallow import ValidationError

from mokkari import character, exceptions


class CharactersList:
    """The CharactersList object contains a list of `Character` objects."""

    def __init__(self, response):
        """Initialize a new CharactersList."""
        self.characters = []

        schema = character.CharacterSchema()
        for character_dict in response["results"]:
            try:
                result = schema.load(character_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.characters.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.characters)

    def __len__(self):
        """Return the length of the object."""
        return len(self.characters)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.characters[index]
