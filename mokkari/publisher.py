from marshmallow import INCLUDE, Schema, fields, post_load


class Publisher:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class PublisherSchema(Schema):
    """ Schema for the Publisher API."""
    id = fields.Int()
    founded = fields.Int()
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Publisher` object
        :rtype: Publisher
        """
        return Publisher(**data)
