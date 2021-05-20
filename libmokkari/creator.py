from marshmallow import INCLUDE, Schema, fields, post_load


class Creator:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreatorSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    birth = fields.Date(allow_none=True)
    death = fields.Date(allow_none=True)
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Str()

    class Meta:
        unknown = INCLUDE
        dateformat = "%Y-%m-%d"

    @post_load
    def make(self, data, **kwargs):
        return Creator(**data)
