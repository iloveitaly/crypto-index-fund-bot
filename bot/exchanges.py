import math
import typing as t
from decimal import Decimal

# https://python-binance.readthedocs.io/en/latest/market_data.html
# https://binance-docs.github.io/apidocs/spot/en/#change-log
# https://github.com/binance-us/binance-official-api-docs
# https://dev.binance.vision/
from binance.client import Client as BinanceClient

from . import utils
from .data_types import CryptoBalance, CryptoData, SupportedExchanges
from .supported_exchanges.binance import *
from .supported_exchanges.coinbase import *
from .user import User
from .utils import log


def portfolio(exchange: SupportedExchanges, user: User) -> t.List[CryptoBalance]:
    mapping = {
        SupportedExchanges.BINANCE: binance_portfolio,
        # SupportedExchanges.COINBASE: coinbase_portfolio,
    }

    return mapping[exchange](user)


def purchase_minimum(exchange: SupportedExchanges) -> Decimal:
    mapping = {
        SupportedExchanges.BINANCE: binance_purchase_minimum,
        # SupportedExchanges.COINBASE: coinbase_purchase_minimum,
    }

    return mapping[exchange]()


def open_orders(exchange: SupportedExchanges, user: User) -> t.List[ExchangeOrder]:
    mapping = {
        SupportedExchanges.BINANCE: binance_open_orders,
        # SupportedExchanges.COINBASE: coinbase_open_orders,
    }

    return mapping[exchange](user)


def market_sell(exchange: SupportedExchanges, user: User, symbol: str, purchasing_currency: str, amount: Decimal):
    mapping = {
        SupportedExchanges.BINANCE: binance_market_sell,
        # SupportedExchanges.COINBASE: coinbase_market_sell,
    }

    return mapping[exchange](user, symbol, purchasing_currency, amount)


def cancel_order(exchange: SupportedExchanges, user: User, order: ExchangeOrder):
    mapping = {
        SupportedExchanges.BINANCE: binance_cancel_order,
        # SupportedExchanges.COINBASE: coinbase_cancel_order,
    }

    return mapping[exchange](user, order)


def limit_buy(exchange: SupportedExchanges, user: User, purchasing_currency: str, symbol: str, quantity: Decimal, price: Decimal):
    mapping = {
        SupportedExchanges.BINANCE: binance_limit_buy,
        # SupportedExchanges.COINBASE: coinbase_limit_buy,
    }

    return mapping[exchange](user, symbol, purchasing_currency, quantity, price)


def market_buy(exchange: SupportedExchanges, user: User, purchasing_currency: str, symbol: str, amount: Decimal):
    mapping = {
        SupportedExchanges.BINANCE: binance_market_buy,
        # SupportedExchanges.COINBASE: coinbase_limit_buy,
    }

    return mapping[exchange](user, symbol, purchasing_currency, amount)


def can_buy_amount_in_exchange(symbol: str):
    binance_symbol_info = binance_get_symbol_info(symbol)

    if binance_symbol_info is None:
        log.warn("symbol did not return any data", symbol=symbol)
        return False

    # the min notional amount specified on the symbol data is the min in USD
    # that needs to be purchased. Most of the time, the minimum is enforced by
    # the binance-wide minimum, but this is not always the case.

    if binance_symbol_info["status"] != "TRADING":
        log.info("symbol is not trading, skipping", symbol=symbol)
        return False

    return True


def can_buy_in_exchange(exchange: SupportedExchanges, symbol: str, purchasing_currency: str) -> bool:
    mapping = {"binance": can_buy_in_binance, "coinbase": can_buy_in_coinbase}

    return mapping[exchange](symbol, purchasing_currency)


def price_of_symbol(symbol: str, purchasing_currency: str) -> Decimal:
    """
    This method is used to calculate the price of a cryptocurrency for market cap calculation.

    It will use prices from (a) binance (b) coinmarketcap. The goal is to get *a* price, even if it's not perfect.
    This is why the exchange type is not specified in this method.
    """

    if purchasing_currency != "USD":
        raise ValueError("only USD purchasing currency is currently supported")

    binance_trading_pair = symbol + purchasing_currency

    if price := binance_price_for_symbol(binance_trading_pair):
        return price
    else:
        log.warn("price not available in binance, pulling from coinmarket cap", symbol=symbol)

        from . import market_cap

        return Decimal(market_cap.coinmarketcap_data_for_symbol(symbol)["quote"][purchasing_currency]["price"])
