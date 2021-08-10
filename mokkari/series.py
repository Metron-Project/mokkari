from marshmallow import INCLUDE, Schema, fields, post_load


class SeriesType:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeriesTypeSchema(Schema):
    id = fields.Int()
    name = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`SeriesType` object
        :rtype: SeriesType
        """
        return SeriesType(**data)


class Series:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeriesSchema(Schema):
    """ Schema for the Series API."""

    id = fields.Int()
    name = fields.Str()
    sort_name = fields.Str()
    volume = fields.Int()
    series_type = fields.Nested(SeriesTypeSchema)
    publisher = fields.Int(attribute="publisher_id")
    year_began = fields.Int()
    year_end = fields.Int()
    desc = fields.Str()
    issue_count = fields.Int()
    image = fields.Url()
    display_name = fields.Str(data_key="__str__")

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Series` object
        :rtype: Series
        """
        return Series(**data)
