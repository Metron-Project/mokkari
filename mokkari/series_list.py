from marshmallow import ValidationError

from mokkari import exceptions, series


class SeriesList:
    def __init__(self, response):
        self.series = []

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

    def __getitem__(self, index: int):
        return self.series[index]
