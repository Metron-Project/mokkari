"""
Series module.

This module provides the following classes:

- SeriesType
- SeriesTypeSchema
- Series
- SeriesSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load


class SeriesType:
    """
    The SeriesType object contains information for type of series.

    :param `**kwargs`: The keyword arguments is used for setting series type data.
    """

    def __init__(self, **kwargs):
        """Intialize a new SeriesType."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeriesTypeSchema(Schema):
    """Schema for the Series Type."""

    id = fields.Int()
    name = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the SeriesType object.

        :param data: Data from Metron response.

        :returns: :class:`SeriesType` object
        :rtype: SeriesType
        """
        return SeriesType(**data)


class Series:
    """
    The Series object contains information for comic series.

    :param `**kwargs`: The keyword arguments is used for setting series data.
    """

    def __init__(self, **kwargs):
        """Intialize a new Series."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeriesSchema(Schema):
    """
    Schema for the Series API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    sort_name = fields.Str()
    volume = fields.Int()
    series_type = fields.Nested(SeriesTypeSchema)
    publisher = fields.Int(attribute="publisher_id")
    year_began = fields.Int()
    year_end = fields.Int(allow_none=True)
    desc = fields.Str()
    issue_count = fields.Int()
    image = fields.Url()
    display_name = fields.Str(data_key="__str__")
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be included."""

        unknown = INCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Series object.

        :param data: Data from Metron response.

        :returns: :class:`Series` object
        :rtype: Series
        """
        return Series(**data)
