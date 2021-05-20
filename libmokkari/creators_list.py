import itertools

from marshmallow import ValidationError

from . import creator, exceptions


class CreatorsList:
    def __init__(self, response) -> None:
        self.creators = []
        self.response = response

        schema = creator.CreatorSchema()
        for creator_dict in response["results"]:
            try:
                result = schema.load(creator_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.creators.append(result)

    def __iter__(self):
        return iter(self.creators)

    def __len__(self):
        return len(self.creators)

    def __getitem__(self, index):
        try:
            return next(itertools.islice(self.creators, index, index + 1))
        except TypeError:
            return list(
                itertools.islice(self.creators, index.start, index.stop, index.step)
            )
