import unittest
from decimal import Decimal
from test.conftest import mocked_order_result
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
    # min & max is set to the same value to isolate testing various details
    PURCHASE_MIN = 25

    # initial buys should prioritize coins that take up a large amount of the index first
    @patch.object(binance.client.Client, "order_market_buy", side_effect=mocked_order_result)
    @patch.object(binance.client.Client, "get_open_orders", return_value=[])
    @patch("bot.exchanges.binance_portfolio", return_value=[])
    def test_initial_buy(self, _binance_portfolio_mock, _open_order_mock, order_market_buy_mock):
        from bot.commands import BuyCommand

        user = user_from_env()
        user.external_portfolio = []
        user.purchase_min = self.PURCHASE_MIN
        user.purchase_max = self.PURCHASE_MIN
        user.buy_strategy = MarketBuyStrategy.MARKET

        assert user.external_portfolio == []
        assert set(user.deprioritized_coins) == set(["DOGE", "XRP", "BNB", "STORJ"])
        assert True == user.livemode
        assert self.PURCHASE_MIN == user.purchase_min
        assert self.PURCHASE_MIN == user.purchase_max
        assert MarketBuyStrategy.MARKET == user.buy_strategy
        assert MarketIndexStrategy.MARKET_CAP == user.index_strategy

        BuyCommand.execute(user=user, purchase_balance=Decimal(self.PURCHASE_MIN * 3))

        # make sure the user minimum is respected
        for mock_call in order_market_buy_mock.mock_calls:
            assert float(mock_call.kwargs["quoteOrderQty"]) == self.PURCHASE_MIN

        all_order_tokens = [mock_call.kwargs["symbol"] for mock_call in order_market_buy_mock.mock_calls]

        # top market tokens should be prioritized
        assert set(all_order_tokens) == set(["BTCUSD", "ETHUSD", "ADAUSD"])

    def test_maximum_purchase_limit(self):
        pass

    # ensure that the target amount is adjusted by the currently owned amount of a token
    def test_does_not_exceed_target(self):
        pass

    @patch.object(binance.client.Client, "order_market_buy", side_effect=mocked_order_result)
    @patch.object(binance.client.Client, "get_open_orders", return_value=[])
    def test_percentage_allocation_limit(self, _open_order_mock, order_market_buy_mock):
        number_of_purchases = 10

        # customized purchase min since we are testing with some live user data where the minimum was lower
        purchase_min = 10

        user = user_from_env()
        user.allocation_drift_percentage_limit = 5
        user.external_portfolio = []
        user.purchase_min = purchase_min
        user.purchase_max = purchase_min

        assert user.external_portfolio == []
        assert user.allocation_drift_multiple_limit == 5
        assert user.allocation_drift_percentage_limit == 5
        assert purchase_min == user.purchase_min
        assert purchase_min == user.purchase_max
        assert MarketIndexStrategy.MARKET_CAP == user.index_strategy
        assert user.exchanges == [SupportedExchanges.BINANCE]
        assert True == user.livemode

        BuyCommand.execute(user=user, purchase_balance=Decimal(purchase_min * number_of_purchases))

        # TODO this should be extracted out into some helper
        for mock_call in order_market_buy_mock.mock_calls:
            assert float(mock_call.kwargs["quoteOrderQty"]) == purchase_min

        # in this example portfolio:
        #   - BTC & ETH are held, but are > 5% off the target allocation
        #   - AVAX is unowned
        #   - HNT is unowned
        #   - AXS, GRT, UNI is way off the target allocation
        #   - FIL, ATOM, AAVE, ALGO have all dropped within the last month

        all_order_tokens = [mock_call.kwargs["symbol"] for mock_call in order_market_buy_mock.mock_calls]
        assert len(all_order_tokens) == number_of_purchases
        assert ["BTCUSD", "ETHUSD", "AVAXUSD", "HNTUSD", "AXSUSD", "UNIUSD", "FILUSD", "ATOMUSD", "AAVEUSD", "ALGOUSD"] == all_order_tokens

    # does a portfolio overallocated on a specific token still purchase tokens that capture much of the market cap?
    @patch.object(binance.client.Client, "order_market_buy", side_effect=mocked_order_result)
    @patch.object(binance.client.Client, "get_open_orders", return_value=[])
    @patch("bot.exchanges.binance_portfolio", return_value=[])
    def test_off_allocation_portfolio(self, _binance_portfolio_mock, _open_order_mock, order_market_buy_mock):
        number_of_orders = 4

        user = user_from_env()
        user.purchase_min = self.PURCHASE_MIN
        user.purchase_max = self.PURCHASE_MIN
        user.buy_strategy = MarketBuyStrategy.MARKET
        user.allocation_drift_multiple_limit = 5
        user.external_portfolio = [  # type: ignore
            {"symbol": "DOGE", "amount": Decimal("1000000")},
            {"symbol": "ETH", "amount": Decimal("0.01")},
            {"symbol": "BTC", "amount": Decimal("0.01")},
        ]

        assert set(user.deprioritized_coins) == set(["DOGE", "XRP", "BNB", "STORJ"])
        assert True == user.livemode
        assert self.PURCHASE_MIN == user.purchase_min
        assert self.PURCHASE_MIN == user.purchase_max
        assert MarketBuyStrategy.MARKET == user.buy_strategy
        assert MarketIndexStrategy.MARKET_CAP == user.index_strategy
        assert None == user.allocation_drift_percentage_limit

        BuyCommand.execute(user=user, purchase_balance=Decimal(self.PURCHASE_MIN * number_of_orders))

        all_order_tokens = [mock_call.kwargs["symbol"] for mock_call in order_market_buy_mock.mock_calls]

        # top market tokens should be prioritized
        assert len(all_order_tokens) == number_of_orders
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
        user.buy_strategy = MarketBuyStrategy.LIMIT

        assert user.livemode == False
        assert user.cancel_stale_orders == True
        assert user.buy_strategy == MarketBuyStrategy.LIMIT

        BuyCommand.execute(user=user)

    def test_not_buying_open_orders(self):
        pass
