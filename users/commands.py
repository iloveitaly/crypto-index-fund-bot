from utils import log

from commands.buy import BuyCommand
from .models import User
import django.utils.timezone

class InitiateUserBuysCommand:
  @classmethod
  def execute(cls):
    for user in User.objects.iterator():
      bot_user = user.bot_user()

      # TODO should set structlog context to user

      log.info("initiating buys for user", user=user)
      BuyCommand.execute(bot_user)

      user.date_checked = django.utils.timezone.now()
      user.save()
