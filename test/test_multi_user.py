import unittest
import pytest
from unittest.mock import patch

from users.models import User
import users.tasks
import bot.commands

# @pytest.fixture
# def celery_enable_logging():
#     return True

@pytest.fixture
# # @pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'memory://',
        # 'result_backend': 'redis://'
    }

@pytest.mark.django_db
class TestMultiUser(unittest.TestCase):
  # @pytest.mark.celery(CELERY_ALWAYS_EAGER=True)
  # @patch('bot.commands.BuyCommand.execute')
  @patch.object(bot.commands.BuyCommand, 'execute')
  def test_performs_market_buy(self, buy_command_mock):
    user_1 = User.objects.create(name="user 1")
    user_1 = User.objects.create(name="user 2")

    # users.tasks.initiate_user_buys.delay()
    # breakpoint()
    users.tasks.initiate_user_buys()

    assert buy_command_mock.call_count == 2
