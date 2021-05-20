from marshmallow import INCLUDE, Schema, fields, post_load


class Series:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeriesSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    sort_name = fields.Str()
    volume = fields.Int()
    # series_type
    # publisher
    year_began = fields.Int()
    year_end = fields.Int()
    desc = fields.Str()
    issue_count = fields.Int()
    image = fields.Url()

    class Meta:
        unknown = INCLUDE

    @post_load
    def make(self, data, **kwargs):
        return Series(**data)
