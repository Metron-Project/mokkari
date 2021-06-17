from marshmallow import INCLUDE, Schema, fields, post_load


class Arc:
    """
    The Arc object contains information for story arcs.

    :param `**kwargs`: The keyword arguments is used for setting arc data from Metron.
    """

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
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Arc` object
        :rtype: Arc
        """
        return Arc(**data)
