import itertools

from marshmallow import ValidationError

from mokkari import exceptions, series


class SeriesList:
    def __init__(self, response):
        self.series = []
        self.response = response

        schema = series.SeriesSchema()
        for series_dict in response["results"]:
            try:
                result = schema.load(series_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.series.append(result)

    def __iter__(self):
        return iter(self.series)

    def __len__(self):
        return len(self.series)

    def __getitem__(self, index):
        try:
            return next(itertools.islice(self.series, index, index + 1))
        except TypeError:
            return list(
                itertools.islice(self.series, index.start, index.stop, index.step)
            )
