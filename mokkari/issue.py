"""
Issue module.

This module provides the following classes:

- Role
- RolesSchema
- RoleList
- Credit
- CreditsSchema
- Issue
- IssueSchema
- IssuesList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import exceptions
from mokkari.arc import ArcSchema
from mokkari.character import CharacterSchema
from mokkari.publisher import PublisherSchema
from mokkari.rating import RatingSchema
from mokkari.reprint import ReprintSchema
from mokkari.series import SeriesSchema
from mokkari.team import TeamSchema
from mokkari.variant import VariantSchema


class Role:
    """
    The Role object contains information for creators' role.

    Args:
        **kwargs (Any): The keyword arguments is used for setting role data from Metron.

    Attributes:
        id (int): The Metron identification number for the role.
        name (str): The name of the role.
    """

    def __init__(self, **kwargs):
        """Initialize a new Role."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class RolesSchema(Schema):
    """Schema for the Roles."""

    id = fields.Int()
    name = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Role object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Role` object.
        """
        return Role(**data)


class RoleList:
    """
    The :obj:`RoleList` object contains a list of roles.

    Attributes:
        id (int): The Metron identification number for the role.
        name (str): The name of the role.

    Returns:
        A list of roles.
    """

    def __init__(self, response):
        """Initialize a new RoleList."""
        self.roles = []

        schema = RolesSchema()
        for role_dict in response["results"]:
            try:
                result = schema.load(role_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

            self.roles.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.roles)

    def __len__(self):
        """Return the length of the object."""
        return len(self.roles)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.roles[index]


class Credit:
    """
    The Credit object contains information for creators credits for an issue.

    Args:
        **kwargs (Any): The keyword arguments is used for setting credits data from Metron.

    Attributes:
        id (int): The Metron identification number for the credit.
        creator (str): The name of the creator.
        role (RoleList): A list of roles for the creator.
    """

    def __init__(self, **kwargs):
        """Initialize a new Credit."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreditsSchema(Schema):
    """Schema for the Credits."""

    id = fields.Int()
    creator = fields.Str()
    role = fields.Nested(RolesSchema, many=True)

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Credit object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Credit` object.
        """
        return Credit(**data)


class Issue:
    """
    The Issue object contains information for an issue.

    Args:
        **kwargs (Any): The keyword arguments is used for setting creator data from Metron.

    Attributes:
        id (int): The Metron identification number for the creator.
        publisher (Publisher): The publisher information for the issue.
        series (Series): The series information for the issue.
        number (str): The issue number.
        collection_title (str): The title of a Trade Paperback.
        story_titles (list[str]): A list of stories contained in the issue.
        cover_date (date): The cover date of the issue.
        store_date (date, optional): The date the issue went for sale.
        price (decimal): The price of the issue.
        rating (Rating): The issue rating.
        sku (str): Stock keeping unit for the issue.
        upc (str): UPC barcode for the issue.
        page_count (int): Number of pages for the issue.
        desc (str): Summary description for the issue.
        image (url): The url for a cover image associated with the issue.
        arcs (list[:obj:`Arc`]): A list of story arcs.
        credits (list[:obj:`Credit`]): A list of creator credits for the issue.
        characters (list[:obj:`Character`]): A list of characters who appear in the issue.
        teams (list[:obj:`Team`]): A list of teams who appear in the issue.
        reprints (list[:obj:`Reprint`]): A list of reprinted issue contained in the issue.
        issue_name (str): The name used to identified the issue.
        variants (list[:obj:`Variant`]): A list of variant covers for the issue.
        modified (datetime): The date/time the issue was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Issue."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class IssueSchema(Schema):
    """
    Schema for the Issue API.

    .. versionchanged:: 0.1.6

        - ``name`` field  changed to ``story_titles``
        - ``__str__`` field change to ``issue_name``

    .. versionchanged:: 0.2.0
        Added ``price`` and ``sku`` fields

    .. versionchanged:: 0.2.2
        Added ``upc`` field

    .. versionchanged:: 0.2.4

        - Added ``page_count`` field
        - Changed ``price`` field from a string to float value.

    .. versionchanged:: 1.0.0

        - Changed ``price`` field to a decimal type.
        - Added ``modified`` field

    .. versionchanged:: 2.1.0

        - Add ``reprints`` field

    .. versionadded:: 2.2.2

        - Add ``collection_title`` field

    .. versionchanged:: 2.3.0

        - Removed ``volume`` field. The series object will have that information.

    .. versionchanged:: 2.3.2

        - Added ``rating`` field.
    """

    id = fields.Int()
    publisher = fields.Nested(PublisherSchema)
    series = fields.Nested(SeriesSchema)
    number = fields.Str()
    collection_title = fields.Str(allow_none=True, data_key="title")
    story_titles = fields.List(fields.Str(allow_none=True), data_key="name")
    cover_date = fields.Date()
    store_date = fields.Date(allow_none=True)
    price = fields.Decimal(places=2, allow_none=True)
    rating = fields.Nested(RatingSchema)
    sku = fields.Str()
    upc = fields.Str()
    page_count = fields.Int(allow_none=True, data_key="page")
    desc = fields.Str(allow_none=True)
    image = fields.URL(allow_none=True)
    arcs = fields.Nested(ArcSchema, many=True)
    credits = fields.Nested(CreditsSchema, many=True)
    characters = fields.Nested(CharacterSchema, many=True)
    teams = fields.Nested(TeamSchema, many=True)
    reprints = fields.Nested(ReprintSchema, many=True)
    issue_name = fields.Str(data_key="issue")
    variants = fields.Nested(VariantSchema, many=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the issue object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            An :obj:`Issue` object.
        """
        return Issue(**data)


class IssuesList:
    """
    The :obj:`IssuesList` object contains a list of issues.

    Attributes:
        id (int): The Metron identification number for the issue.
        issue (str): The name of the issue.
        cover_date (date): The cover date for the issue.
        modified (datetime): The date/time the creator was last changed.

    Returns:
        A list of issues.
    """

    def __init__(self, response):
        """Initialize a new IssuesList."""
        self.issues = []

        schema = IssueSchema()
        for issue_dict in response["results"]:
            try:
                result = schema.load(issue_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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
