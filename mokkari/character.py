"""
Character module.

This module provides the following classes:

- Character
- CharacterSchema
- CharactersList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import creator, exceptions, team


class Character:
    """
    The Character object contains information for characters.

    Args:
        **kwargs (Any): The keyword arguments is used for setting character data from Metron.

    Attributes:
        id (int): The Metron identification number for the character.
        name (str): The name of the character.
        alias (list[str]): List of aliases the character may have.
        desc (str): The description of the character.
        image (url): The url for an image associated with the character.
        creators (list[Creator]): A list of creators for the character.
        teams (list[Team]): A list of teams the character is a member of.
        modified (datetime): The date/time the character was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Character."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CharacterSchema(Schema):
    """
    Schema for the Character API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field

    .. versionchanged:: 2.0.2
        - Removed ``wikipedia`` field
    """

    id = fields.Int()
    name = fields.Str()
    alias = fields.List(fields.Str)
    desc = fields.Str()
    image = fields.Url(allow_none=True)
    creators = fields.Nested(creator.CreatorSchema, many=True)
    teams = fields.Nested(team.TeamSchema, many=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the character object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Character` object
        """
        return Character(**data)


class CharactersList:
    """
    The :obj:`CharactersList` object contains a list of characters.

    Attributes:
        id (int): The Metron identification number for the character.
        name (str): The name of the character.
        modified (datetime): The date/time the character was last changed.

    Returns:
        A list of characters.
    """

    def __init__(self, response):
        """Initialize a new CharactersList."""
        self.characters = []

        schema = CharacterSchema()
        for character_dict in response["results"]:
            try:
                result = schema.load(character_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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
