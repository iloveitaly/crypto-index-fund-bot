import json

from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


# for ensuring all floats are parsed as decimals
class CustomJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        from decimal import Decimal

        kwargs["parse_float"] = Decimal
        super().__init__(*args, **kwargs)


class User(models.Model):
    # TODO these are not stored in `preferences` since we want to encrypt them in the future
    # django requires an explicit field length; the key sizes here are probably much smaller
    binance_api_key = EncryptedCharField(max_length=100, null=True)
    binance_secret_key = EncryptedCharField(max_length=100, null=True)

    external_portfolio = models.JSONField(default=list, decoder=CustomJSONDecoder)
    preferences = models.JSONField(default=dict)
    name = models.CharField(max_length=100)
    date_checked = models.DateTimeField(null=True)
    last_ordered_at = models.DateTimeField(null=True)
    disabled = models.BooleanField(default=False)

    def bot_user(self):
        # copy all fields to the other instance of user currently used by the bot
        # eventually, we'll want to merge the two but let's just get this working first

        # TODO really terrible that we are using the same name here for both users
        from bot.user import User as BotUser

        bot_user = BotUser()
        bot_user.binance_api_key = self.binance_api_key
        bot_user.binance_secret_key = self.binance_secret_key
        bot_user.external_portfolio = self.external_portfolio

        for key, val in self.preferences.items():
            setattr(bot_user, key, val)

        return bot_user

    def __repr__(self):
        return f"<{self} {self.name} {self.date_checked}>"
