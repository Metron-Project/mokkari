"""
Arc module.

This module provides the following classes:

- Arc
- ArcSchema
- ArcsList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import exceptions


class Arc:
    """
    The Arc object contains information for story arcs.

    :param `**kwargs`: The keyword arguments is used for setting arc data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Arc."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class ArcSchema(Schema):
    """
    Schema for the Arc API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    desc = fields.Str()
    image = fields.Url()
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron response.

        :returns: :class:`Arc` object
        :rtype: Arc
        """
        return Arc(**data)


class ArcsList:
    """The ArcsList object contains a list of `Arc` objects."""

    def __init__(self, response):
        """Initialize a new ArcsList."""
        self.arcs = []

        schema = ArcSchema()
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
