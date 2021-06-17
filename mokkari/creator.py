from marshmallow import INCLUDE, Schema, fields, post_load


class Creator:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreatorSchema(Schema):
    """ Schema for the Creator API."""

    id = fields.Int()
    name = fields.Str()
    birth = fields.Date(allow_none=True)
    death = fields.Date(allow_none=True)
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()

    class Meta:
        unknown = INCLUDE
        dateformat = "%Y-%m-%d"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Creator` object
        :rtype: Creator
        """
        return Creator(**data)
