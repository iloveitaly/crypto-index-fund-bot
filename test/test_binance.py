import pytest
import unittest

import bot.exchanges as exchanges


@pytest.mark.vcr
class TestBinance(unittest.TestCase):
    # this invariant is important to the bot making correct decisions
    def test_individual_and_batch_symbols(self):
        for target_trading_pair in ["BTCUSD", "ETHUSD"]:
            symbol_info_from_batch = exchanges.binance_get_symbol_info(target_trading_pair)
            symbol_info_directly = exchanges.public_binance_client().get_symbol_info(target_trading_pair)

            assert symbol_info_from_batch == symbol_info_directly
