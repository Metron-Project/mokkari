"""
Series module.

This module provides the following classes:

- SeriesType
- SeriesTypeSchema
- Series
- SeriesSchema
- SeriesList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import exceptions
from mokkari.publisher import PublisherSchema


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


class AssociatedSeries:
    """
    The AssociateSeries objects contains any associated series to the primary series.

    :param `**kwargs`: he keyword arguments is used for setting associated series data.
    """

    def __init__(self, **kwargs):
        """Intialize a new AssociatedSeries."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class AssociatedSeriesSchema(Schema):
    """Schema for Associated Series."""

    id = fields.Int()
    name = fields.Str(data_key="__str__")

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the AssociatedSeries object.

        :param data: Data from Metron response.

        :returns: :class:`AssociatedSeries` object
        :rtype: AssociatedSeries
        """
        return AssociatedSeries(**data)


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

    .. versionchanged:: 1.0.5

        - Added ``associated`` field

    .. versionchanged:: 2.0.0

        - Changed ``publisher`` to a nested field.
    """

    id = fields.Int()
    name = fields.Str()
    sort_name = fields.Str()
    volume = fields.Int()
    series_type = fields.Nested(SeriesTypeSchema)
    publisher = fields.Nested(PublisherSchema)
    year_began = fields.Int()
    year_end = fields.Int(allow_none=True)
    desc = fields.Str()
    issue_count = fields.Int()
    image = fields.Url()
    display_name = fields.Str(data_key="__str__")
    associated = fields.Nested(AssociatedSeriesSchema, many=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
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


class SeriesList:
    """The SeriesList object contains a list of `Series` objects."""

    def __init__(self, response):
        """Initialize a new SeriesList."""
        self.series = []

        schema = SeriesSchema()
        for series_dict in response["results"]:
            try:
                result = schema.load(series_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

            self.series.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.series)

    def __len__(self):
        """Return the length of the object."""
        return len(self.series)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.series[index]
