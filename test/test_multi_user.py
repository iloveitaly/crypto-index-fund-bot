import unittest
import pytest
from unittest.mock import patch

from users.models import User
import users.tasks
import bot.commands

# Specifying `@pytest.mark.usefixtures('celery_session_worker')` causes issues with database cleaning

@pytest.mark.django_db
class TestMultiUser(unittest.TestCase):
  @patch.object(bot.commands.BuyCommand, 'execute')
  def test_performs_market_buy(self, buy_command_mock):
    user_1 = User.objects.create(name="user 1")
    user_1 = User.objects.create(name="user 2")

    # users.tasks.initiate_user_buys.delay()
    # breakpoint()
    users.tasks.initiate_user_buys.delay()

    assert buy_command_mock.call_count == 2
