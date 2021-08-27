from django.db import models

class User(models.Model):
  # django requires an explicit field length; the key sizes here are probably much smaller
  binance_api_key = models.CharField(max_length=100, null=True)
  binance_secret_key = models.CharField(max_length=100, null=True)

  external_portfolio = models.JSONField(default=dict)
  preferences = models.JSONField(default=dict)
  name = models.CharField(max_length=100)
  date_checked = models.DateTimeField(null=True)

  def bot_user(self):
    # copy all fields to the other instance of user currently used by the bot
    # eventually, we'll want to merge the two but let's just get this working first

    # TODO really terrible that we are using the same name here for both users
    from user import User as BotUser

    bot_user = BotUser()
    bot_user.binance_api_key = self.binance_api_key
    bot_user.binance_secret_key = self.binance_secret_key
    bot_user.external_portfolio = self.external_portfolio

    for k, v in self.preferences:
      setattr(bot_user, k, v)

    return bot_user