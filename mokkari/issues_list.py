"""
IssuesList module.

This module provides the following classes:

- IssuesList
"""
from marshmallow import ValidationError

from mokkari import exceptions, issue


class IssuesList:
    """The IssuesList object contains a list of `Issue` objects."""

    def __init__(self, response):
        """Initialize a new IssuesList."""
        self.issues = []

        schema = issue.IssueSchema()
        for issue_dict in response["results"]:
            try:
                result = schema.load(issue_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.issues.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.issues)

    def __len__(self):
        """Return the length of the object."""
        return len(self.issues)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.issues[index]
