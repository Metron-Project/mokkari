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
from mokkari.genre import GenreSchema
from mokkari.publisher import PublisherSchema


class SeriesType:
    """
    The SeriesType object contains information for type of series.

    Args:
        **kwargs (Any): The keyword arguments is used for setting series type data from Metron.

    Attributes:
        id (int): The Metron identification number for the series type.
        name (str): The name of the series type.
    """

    def __init__(self, **kwargs):
        """Initialize a new SeriesType."""
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

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`SeriesType` object.
        """
        return SeriesType(**data)


class SeriesTypeList:
    """
    The :obj:`SeriesTypeList` object contains a list of series types.

    Attributes:
        id (int): The Metron identification number for the series type.
        name (str): The name of the series type.

    Returns:
        A list of series types.
    """

    def __init__(self, response):
        """Initialize a new SeriesTypeList."""
        self.series = []

        schema = SeriesTypeSchema()
        for series_type_dict in response["results"]:
            try:
                result = schema.load(series_type_dict)
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


class AssociatedSeries:
    """
    The AssociateSeries objects contains any associated series to the primary series.

    Args:
        **kwargs (Any): The keyword arguments is used for setting associated series data
        from Metron.

    Attributes:
        id (int): The Metron identification number for the associated series.
        name (str): The name of the associated series.
    """

    def __init__(self, **kwargs):
        """Initialize a new AssociatedSeries."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class AssociatedSeriesSchema(Schema):
    """Schema for Associated Series."""

    id = fields.Int()
    name = fields.Str(data_key="series")

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the AssociatedSeries object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            An :obj:`AssociatedSeries` object.
        """
        return AssociatedSeries(**data)


class Series:
    """
    The Series object contains information for comic series.

    Args:
        **kwargs (Any): The keyword arguments is used for setting series data from Metron.

    Attributes:
        id (int): The Metron identification number for the series.
        name (str): The name of the series.
        sort_name (str): The name used to sort a series.
        volume (int): The volume number for a series.
        publisher (Publisher): The publisher of the series.
        year_began (int): The cover year the series began.
        year_end (int, optional): The cover year in which the series ended.
        desc (str): A summary description of the series.
        issue_count (int): The number of issues the series contains.
        display_name (str): The display name for the series.
        genres (list[Genre]): A list of genres for the series.
        associated (list[AssociatedSeries]): A list of of series associated with the
        primary series.
        modified (datetime): The date/time the series was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Series."""
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

    .. versionchanged:: 2.0.3
        - Changed ``series_type`` to a string field.

    .. versionchanged:: 2.0.4
        - Reverted ``series_type`` back to a nested field.

    .. versionchanged:: 2.1.1
        Added ``genres`` fields
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
    image = fields.Url(allow_none=True)
    display_name = fields.Str(data_key="series")
    genres = fields.Nested(GenreSchema, many=True)
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

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Series` object.
        """
        return Series(**data)


class SeriesList:
    """
    The :obj:`SeriesList` object contains a list of series.

    Attributes:
        id (int): The Metron identification number for the series.
        series (str): The name of the series.
        modified (datetime): The date/time the series was last changed.

    Returns:
        A list of series.
    """

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
