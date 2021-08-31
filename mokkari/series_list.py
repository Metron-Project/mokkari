"""
SeriesList module.

This module provides the following classes:

- SeriesList
"""
from marshmallow import ValidationError

from mokkari import exceptions, series


class SeriesList:
    """The SeriesList object contains a list of `Series` objects."""

    def __init__(self, response):
        """Initialize a new SeriesList."""
        self.series = []

        schema = series.SeriesSchema()
        for series_dict in response["results"]:
            try:
                result = schema.load(series_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

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
