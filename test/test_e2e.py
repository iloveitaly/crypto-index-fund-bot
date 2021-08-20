import unittest
from user import user_from_env
import pytest

import market_cap

from unittest.mock import patch
from click.testing import CliRunner

import binance.client
import market_cap
import main

from data_types import MarketBuyStrategy, MarketIndexStrategy

@pytest.fixture(scope="module")
def vcr_config():
  return {
    "filter_headers": [
      "X-MBX-APIKEY",
      "X-CMC_PRO_API_KEY",

      # headers with random IDs which cause requests not to match
      "x-mbx-uuid",
      "X-Amz-Cf-Id",
      "Via",
      "Date",
      "Strict-Transport-Security"
    ],
    "filter_query_parameters": ["signature", "timestamp"],
    "decode_compressed_response": True,

    # in our case, binance will hit `ping` multiple times
    # https://github.com/kevin1024/vcrpy/issues/516
    "allow_playback_repeats": True
  }

@pytest.mark.vcr
class TestE2E(unittest.TestCase):
  def test_not_buying_open_orders(self):
    pass

  @patch.object(binance.client.Client, 'order_market_buy')
  @patch('market_buy.purchasing_currency_in_portfolio', return_value=60.0)
  def test_market_buy(self, _purchasing_currency_mock, order_market_buy_mock):
    # user preconditions
    user = user_from_env()
    assert True == user.livemode
    assert 30 == user.purchase_min
    assert MarketBuyStrategy.MARKET == user.buy_strategy
    assert MarketIndexStrategy.MARKET_CAP == user.index_strategy

    runner = CliRunner()
    result = runner.invoke(main.buy, [])

    # output is redirected to the result object, let's output for debugging
    print(result.output)

    # assert result.exception is None
    assert result.exit_code == 0

    # 60 should be split into two orders
    assert order_market_buy_mock.call_count == 2
    assert {'symbol': 'ENJUSD', 'newOrderRespType': 'FULL', 'quoteOrderQty': '30.0'} == order_market_buy_mock.mock_calls[0].kwargs
    assert {'symbol': 'MKRUSD', 'newOrderRespType': 'FULL', 'quoteOrderQty': '30.00000'} == order_market_buy_mock.mock_calls[1].kwargs
