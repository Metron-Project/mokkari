import itertools

from marshmallow import ValidationError

from mokkari import arc, exceptions


class ArcsList:
    def __init__(self, response):
        self.arcs = []
        self.response = response

        schema = arc.ArcSchema()
        for arc_dict in response["results"]:
            try:
                result = schema.load(arc_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.arcs.append(result)

    def __iter__(self):
        return iter(self.arcs)

    def __len__(self):
        return len(self.arcs)

    def __getitem__(self, index):
        try:
            return next(itertools.islice(self.arcs, index, index + 1))
        except TypeError:
            return list(
                itertools.islice(self.arcs, index.start, index.stop, index.step)
            )
