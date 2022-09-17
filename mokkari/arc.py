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

    Args:
        **kwargs (Any): The keyword arguments is used for setting arc data from Metron.

    Attributes:
        id (int): The Metron identification number for the story arc.
        name (str): The name of the story arc.
        desc (str): The description of the story arc.
        image (url): The url for an image associated with the story arc.
        modified (datetime): The date/time the story arc was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Arc."""
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
    image = fields.Url(allow_none=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            An :obj:`Arc` object
        """
        return Arc(**data)


class ArcsList:
    """
    The :obj:`ArcsList` object contains a list of story arcs.

    Attributes:
        id (int): The Metron identification number for the story arc.
        name (str): The name of the story arc.
        modified (datetime): The date/time the story arc was last changed.

    Returns:
        A list of story arcs.
    """

    def __init__(self, response):
        """Initialize a new ArcsList."""
        self.arcs = []

        schema = ArcSchema()
        for arc_dict in response["results"]:
            try:
                result = schema.load(arc_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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
