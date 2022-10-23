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

    Args:
        **kwargs (Any): The keyword arguments is used for setting creator data from Metron.

    Attributes:
        id (int): The Metron identification number for the creator.
        name (str): The name of the creator.
        birth (date): The date of birth for the creator.
        death (date): The date of death for the creator.
        desc (str): The description of the creator.
        image (url): The url for an image associated with the creator.
        resource_url (url): The url for the resource.
        modified (datetime): The date/time the creator was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Creator."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreatorSchema(Schema):
    """
    Schema for the Creator API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field

    .. versionchanged:: 2.0.2

        - Removed ``wikipedia`` field

    .. versionchanged:: 2.3.3

        - Added ``resource_url`` field.
    """

    id = fields.Int()
    name = fields.Str()
    birth = fields.Date(allow_none=True)
    death = fields.Date(allow_none=True)
    desc = fields.Str()
    image = fields.Url(allow_none=True)
    resource_url = fields.URL()
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

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Creator` object.
        """
        return Creator(**data)


class CreatorsList:
    """
    The :obj:`CreatorsList` object contains a list of creators.

    Attributes:
        id (int): The Metron identification number for the creator.
        name (str): The name of the creator.
        modified (datetime): The date/time the creator was last changed.

    Returns:
        A list of creators.
    """

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
