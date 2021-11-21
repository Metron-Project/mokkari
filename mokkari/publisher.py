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

    :param `**kwargs`: The keyword arguments is used for setting publisher data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Publisher."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class PublisherSchema(Schema):
    """
    Schema for the Publisher API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    founded = fields.Int()
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Publisher object.

        :param data: Data from Metron response.

        :returns: :class:`Publisher` object
        :rtype: Publisher
        """
        return Publisher(**data)


class PublishersList:
    """The PublishersList object contains a list of `Publisher` objects."""

    def __init__(self, response):
        """Initialize a new PublishersList."""
        self.publishers = []

        schema = PublisherSchema()
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
