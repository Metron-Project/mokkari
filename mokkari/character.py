from marshmallow import INCLUDE, Schema, fields, post_load

from mokkari import creator, team


class Character:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CharacterSchema(Schema):
    """ Schema for the Arc API."""

    id = fields.Int()
    name = fields.Str()
    alias = fields.List(fields.Str)
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    creators = fields.Nested(creator.CreatorSchema, many=True)
    teams = fields.Nested(team.TeamSchema, many=True)

    class Meta:
        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the character object.

        :param data: Data from Metron reponse.

        :returns: :class:`Character` object
        :rtype: Character
        """
        return Character(**data)
