from marshmallow import INCLUDE, Schema, fields, post_load

from mokkari import arc, character, publisher, series, team


class Role:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class RolesSchema(Schema):
    id = fields.Int()
    name = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        return Role(**data)


class Credit:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreditsSchema(Schema):
    id = fields.Int()
    creator = fields.Str()
    role = fields.Nested(RolesSchema, many=True)

    @post_load
    def make_object(self, data, **kwargs):
        return Credit(**data)


class Issue:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class IssueSchema(Schema):
    """ Schema for the Issue API."""
    id = fields.Int()
    publisher = fields.Nested(publisher.PublisherSchema)
    series = fields.Nested(series.SeriesSchema)
    volume = fields.Int()
    number = fields.Str()
    name = fields.List(fields.Str(allow_none=True))
    cover_date = fields.Date()
    store_date = fields.Date(allow_none=True)
    desc = fields.Str(allow_none=True)
    image = fields.URL()
    arcs = fields.Nested(arc.ArcSchema, many=True)
    credits = fields.Nested(CreditsSchema, many=True)
    characters = fields.Nested(character.CharacterSchema, many=True)
    teams = fields.Nested(team.TeamSchema, many=True)

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        return Issue(**data)
