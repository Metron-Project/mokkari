from marshmallow import INCLUDE, Schema, fields, post_load

from mokkari import arc, character, publisher, series, team


class Issue:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class IssueSchema(Schema):
    id = fields.Int()
    publisher = fields.Nested(publisher.PublisherSchema)
    series = fields.Nested(series.SeriesSchema)
    volume = fields.Int()
    number = fields.Str()
    name = fields.List(fields.Str())
    cover_date = fields.Date()
    store_date = fields.Date()
    desc = fields.Str()
    image = fields.URL()
    arcs = fields.Nested(arc.ArcSchema, many=True)
    # credits
    characters = fields.Nested(character.CharacterSchema, many=True)
    teams = fields.Nested(team.TeamSchema, many=True)

    class Meta:
        unknown = INCLUDE

    @post_load
    def make(self, data, **kwargs):
        return Issue(**data)
