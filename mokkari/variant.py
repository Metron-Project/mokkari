from marshmallow import INCLUDE, Schema, fields, post_load


class Variant:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class VariantSchema(Schema):
    """Schema for the Variant API."""

    name = fields.Str()
    sku = fields.Str()
    image = fields.Url()

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Variant` object
        :rtype: Variant
        """
        return Variant(**data)
