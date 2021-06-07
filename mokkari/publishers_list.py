from marshmallow import ValidationError

from mokkari import exceptions, publisher


class PublishersList:
    def __init__(self, response):
        self.publishers = []

        schema = publisher.PublisherSchema()
        for pub_dict in response["results"]:
            try:
                result = schema.load(pub_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.publishers.append(result)

    def __iter__(self):
        return iter(self.publishers)

    def __len__(self):
        return len(self.publishers)

    def __getitem__(self, index: int):
        return self.publishers[index]
