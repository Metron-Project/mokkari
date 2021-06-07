from marshmallow import ValidationError

from mokkari import arc, exceptions


class ArcsList:
    def __init__(self, response):
        self.arcs = []

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

    def __getitem__(self, index: int):
        return self.arcs[index]
