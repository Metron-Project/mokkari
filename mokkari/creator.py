"""
Creator module.

This module provides the following classes:

- Creator
- CreatorSchema
- CreatorsList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import exceptions


class Creator:
    """
    The Creator object contains information for creators.

    :param `**kwargs`: The keyword arguments is used for setting creator data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Creator."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreatorSchema(Schema):
    """
    Schema for the Creator API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field

    .. versionchanged:: 2.0.2
        - Removed ``wikipedia`` field
    """

    id = fields.Int()
    name = fields.Str()
    birth = fields.Date(allow_none=True)
    death = fields.Date(allow_none=True)
    desc = fields.Str()
    image = fields.Url()
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        dateformat = "%Y-%m-%d"
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Creator object.

        :param data: Data from Metron response.

        :returns: :class:`Creator` object
        :rtype: Creator
        """
        return Creator(**data)


class CreatorsList:
    """The CreatorsList object contains a list of `Creator` objects."""

    def __init__(self, response) -> None:
        """Initialize a new CreatorsList."""
        self.creators = []

        schema = CreatorSchema()
        for creator_dict in response["results"]:
            try:
                result = schema.load(creator_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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
