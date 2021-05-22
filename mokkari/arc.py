from marshmallow import INCLUDE, Schema, fields, post_load


class Arc:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class ArcSchema(Schema):
    """ Schema for the Arc API. """
    id = fields.Int()
    name = fields.Str()
    desc = fields.Str()
    image = fields.Url()

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        return Arc(**data)
