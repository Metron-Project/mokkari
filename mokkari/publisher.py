"""
Publisher module.

This module provides the following classes:

- Publisher
- PublisherSchema
- PublishersList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import exceptions


class Publisher:
    """
    The Publisher object contains information for publishers.

    Args:
        **kwargs (Any): The keyword arguments is used for setting publisher data from Metron.

    Attributes:
        id (int): The Metron identification number for the publisher.
        name (str): The name of the publisher.
        founded (int): The year the publisher was founded.
        desc (str): A summary description about the publisher.
        image (url): The url for an image associated with the publisher.
        modified (datetime): The date/time the publisher was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Publisher."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class PublisherSchema(Schema):
    """
    Schema for the Publisher API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field

    .. versionchanged:: 2.0.2

        - Removed ``wikipedia`` field
    """

    id = fields.Int()
    name = fields.Str()
    founded = fields.Int()
    desc = fields.Str()
    image = fields.Url(allow_none=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Publisher object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Publisher` object.
        """
        return Publisher(**data)


class PublishersList:
    """
    The :obj:`PublishersList` object contains a list of publishers.

    Attributes:
        id (int): The Metron identification number for the publisher.
        name (str): The name of the publisher.
        modified (datetime): The date/time the publisher was last changed.

    Returns:
        A list of publishers.
    """

    def __init__(self, response):
        """Initialize a new PublishersList."""
        self.publishers = []

        schema = PublisherSchema()
        for pub_dict in response["results"]:
            try:
                result = schema.load(pub_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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
