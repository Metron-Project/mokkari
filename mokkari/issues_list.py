import itertools

from marshmallow import ValidationError

from mokkari import exceptions, issue


class IssuesList:
    def __init__(self, response):
        self.issues = []
        self.response = response

        schema = issue.IssueSchema()
        for issue_dict in response["results"]:
            try:
                result = schema.load(issue_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.issues.append(result)

    def __iter__(self):
        return iter(self.issues)

    def __len__(self):
        return len(self.issues)

    def __getitem__(self, index):
        try:
            return next(itertools.islice(self.issues, index, index + 1))
        except TypeError:
            return list(
                itertools.islice(self.issues, index.start, index.stop, index.step)
            )
