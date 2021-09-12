import unittest
from unittest.mock import patch

import pytest

import bot.commands
import users.tasks
from users.models import User

# Specifying `@pytest.mark.usefixtures('celery_session_worker')` causes issues with database cleaning


@pytest.mark.django_db
class TestMultiUser(unittest.TestCase):
    @patch.object(bot.commands.BuyCommand, "execute")
    def test_performs_market_buy(self, buy_command_mock):
        user_1 = User.objects.create(name="user 1")
        user_2 = User.objects.create(name="user 2")

        users.tasks.initiate_user_buys.delay()

        assert buy_command_mock.call_count == 2

    def test_external_portfolio(self):
        from decimal import Decimal

        user = User(external_portfolio=[{"symbol": "BTC", "amount": 1.05}])
        user.save()

        fresh_user = User.objects.get(id=user.id)

        assert isinstance(fresh_user.external_portfolio[0]["amount"], Decimal)
