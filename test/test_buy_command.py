import unittest
from decimal import Decimal
from unittest.mock import patch

import binance.client
import pytest

from bot.commands import BuyCommand
from bot.data_types import (
    ExchangeOrder,
    MarketBuyStrategy,
    MarketIndexStrategy,
    OrderTimeInForce,
    OrderType,
    SupportedExchanges,
)
from bot.user import user_from_env


@pytest.mark.vcr
class TestBuyCommand(unittest.TestCase):
    PURCHASE_MIN = 25

    # initial buys should prioritize coins that take up a large amount of the index first
    @patch.object(binance.client.Client, "order_market_buy", return_value={})
    @patch.object(binance.client.Client, "get_open_orders", return_value=[])
    @patch("bot.exchanges.binance_portfolio", return_value=[])
    def test_initial_buy(self, _binance_portfolio_mock, _open_order_mock, order_market_buy_mock):
        from bot.commands import BuyCommand

        user = user_from_env()
        user.external_portfolio = []
        user.purchase_min = self.PURCHASE_MIN

        assert user.external_portfolio == []
        assert set(user.deprioritized_coins) == set(["DOGE", "XRP", "BNB"])
        assert True == user.livemode
        assert self.PURCHASE_MIN == user.purchase_min
        assert MarketBuyStrategy.MARKET == user.buy_strategy
        assert MarketIndexStrategy.MARKET_CAP == user.index_strategy

        BuyCommand.execute(user=user, purchase_balance=Decimal(self.PURCHASE_MIN * 3))

        # make sure the user minimum is respected
        assert float(order_market_buy_mock.mock_calls[0].kwargs["quoteOrderQty"]) == self.PURCHASE_MIN

        all_order_tokens = [mock_call.kwargs["symbol"] for mock_call in order_market_buy_mock.mock_calls]

        # top market tokens should be prioritized
        assert set(all_order_tokens) == set(["BTCUSD", "ETHUSD", "ADAUSD"])

    @patch.object(binance.client.Client, "order_market_buy", return_value={})
    @patch.object(binance.client.Client, "get_open_orders", return_value=[])
    @patch("bot.exchanges.binance_portfolio", return_value=[])
    def test_off_allocation_portfolio(self, _binance_portfolio_mock, _open_order_mock, order_market_buy_mock):
        user = user_from_env()
        user.purchase_min = self.PURCHASE_MIN
        user.external_portfolio = [  # type: ignore
            {"symbol": "DOGE", "amount": Decimal("1000000")},
            {"symbol": "ETH", "amount": Decimal("0.05")},
            {"symbol": "BTC", "amount": Decimal("0.05")},
        ]

        assert set(user.deprioritized_coins) == set(["DOGE", "XRP", "BNB"])
        assert True == user.livemode
        assert self.PURCHASE_MIN == user.purchase_min
        assert MarketBuyStrategy.MARKET == user.buy_strategy
        assert MarketIndexStrategy.MARKET_CAP == user.index_strategy

        BuyCommand.execute(user=user, purchase_balance=Decimal(self.PURCHASE_MIN * 4))

        all_order_tokens = [mock_call.kwargs["symbol"] for mock_call in order_market_buy_mock.mock_calls]

        # top market tokens should be prioritized
        assert set(all_order_tokens) == set(["BTCUSD", "ETHUSD", "ADAUSD", "SOLUSD"])

    @patch(
        "bot.exchanges.open_orders",
        return_value=[
            ExchangeOrder(
                symbol="ADA",
                trading_pair="ADAUSD",
                quantity=Decimal("5.10000000"),
                price=Decimal("2.0000"),
                created_at=1631457393,
                time_in_force=OrderTimeInForce("GTC"),
                type=OrderType("BUY"),
                id="259074455",
                exchange=SupportedExchanges.BINANCE,
            )
        ],
    )
    @patch("bot.exchanges.portfolio", return_value=[])
    def test_cancelling_stale_orders(self, _mock_portfolio, _mock_open_orders):
        user = user_from_env()
        user.livemode = False
        user.cancel_stale_orders = True

        assert user.livemode == False
        assert user.cancel_stale_orders == True
        assert user.buy_strategy == MarketBuyStrategy.LIMIT

        BuyCommand.execute(user=user)

    def test_not_buying_open_orders(self):
        pass
