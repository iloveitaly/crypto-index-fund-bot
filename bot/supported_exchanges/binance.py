import decimal
import functools
import math
import typing as t
from decimal import Decimal

from binance.client import Client as BinanceClient

from .. import utils
from ..data_types import (
    CryptoBalance,
    ExchangeOrder,
    OrderTimeInForce,
    OrderType,
    SupportedExchanges,
)
from ..user import User
from ..utils import log

# binance.us API is difference from binance.com
# https://github.com/binance-us/binance-official-api-docs
# https://docs.binance.us/#introduction

# https://python-binance.readthedocs.io/en/latest/market_data.html
# https://binance-docs.github.io/apidocs/spot/en/#change-log
# https://dev.binance.vision/
# https://algotrading101.com/learn/binance-python-api-guide/
# https://github.com/timggraf/crypto-index-bot seems to have details about binance errors. Need to handle more error types


# initializing a new client actually hits the `ping` endpoint on the API
# which is on of the reasons we want to cache it
@functools.cache
def public_binance_client() -> BinanceClient:
    return BinanceClient("", "", tld="us")


def binance_purchase_minimum() -> Decimal:
    return Decimal(10)


def can_buy_in_binance(symbol: str, purchasing_currency: str) -> bool:
    for coin in binance_all_symbol_info():
        if coin["baseAsset"] == symbol and coin["quoteAsset"] == purchasing_currency:
            return True

    return False


def is_trading_active_for_coin_in_binance(symbol: str, purchasing_currency: str) -> bool:
    paired_symbol = symbol + purchasing_currency
    binance_symbol_info = binance_get_symbol_info(paired_symbol)

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


# TODO is there a way to enforce trading pair via typing?
def binance_price_for_symbol(trading_pair: str) -> Decimal:
    """
    trading_pair must be in the format of "BTCUSD"

    This method will throw an exception if the price does not exist.
    """

    # `symbol` is a trading pair
    # this includes both USDT and USD prices
    # the pair formatting is 'BTCUSD'
    return utils.cached_result(
        "binance_price_for_symbol",
        lambda: {
            price_dict["symbol"]: Decimal(price_dict["price"])
            # `get_all_tickers` is only called once
            for price_dict in public_binance_client().get_all_tickers()
        },
    ).get(trading_pair)


def binance_portfolio(user: User) -> t.List[CryptoBalance]:
    account = user.binance_client().get_account()

    # binance.us does not yet have staking balances
    # result = user.binance_client()._request_margin_api("get", "staking/position", True, data={"product": "STAKING"})

    # TODO return an incomplete CryptoBalance that will be augmented with additional fields later on
    return [
        CryptoBalance(
            symbol=balance["asset"],
            amount=Decimal(balance["free"]),
            # to satisify typer; hopefully there is a better way to do this in the future
            usd_price=Decimal(0),
            usd_total=Decimal(0),
            percentage=Decimal(0),
            target_percentage=Decimal(0),
        )
        for balance in account["balances"]
        if float(balance["free"]) > 0
    ]


def binance_open_orders(user: User) -> t.List[ExchangeOrder]:
    """
        [
        {
            'symbol': 'HNTUSD',
            'orderId': 123123123,
            'orderListId': -1,
            'clientOrderId': 'web_123longsha123',
            'price': '45.0000',
            'origQty': '10.00000000',
            'executedQty': '0.00000000',
            'cummulativeQuoteQty': '0.0000',
            'status': 'NEW',
            'timeInForce': 'GTC',
            'type': 'LIMIT',
            'side': 'SELL',
            'stopPrice': '0.0000',
            'icebergQty': '0.00000000',
            'time': 1629643256714,
            'updateTime': 1629643256714,
            'isWorking': True,
            'origQuoteOrderQty': '0.0000'
        }
    ]
    """

    return [
        ExchangeOrder(
            # TODO PURCHASING_CURRENCY should make this dynamic for different purchasing currencies
            # cut off the 'USD' at the end of the symbol
            symbol=order["symbol"][:-3],
            trading_pair=order["symbol"],
            quantity=Decimal(order["origQty"]),
            price=Decimal(order["price"]),
            # binance represents time in milliseconds
            created_at=int(Decimal(order["time"]) / 1000),
            time_in_force=OrderTimeInForce(order["timeInForce"]),
            type=OrderType(order["side"]),
            id=order["orderId"],
            exchange=SupportedExchanges.BINANCE,
        )
        for order in user.binance_client().get_open_orders()
        if order["side"] == BinanceClient.SIDE_BUY
    ]


# TODO maybe document struct of dict?
def binance_all_symbol_info() -> t.List[t.Dict]:
    return utils.cached_result(
        "binance_all_symbol_info",
        # exchange info includes filters, status, etc but does NOT include pricing data
        lambda: public_binance_client().get_exchange_info()["symbols"],
    )


def binance_get_symbol_info(trading_pair: str):
    return next((symbol_info for symbol_info in binance_all_symbol_info() if symbol_info["symbol"] == trading_pair))


def binance_normalize_purchase_amount(amount: t.Union[str, Decimal], symbol: str) -> str:
    symbol_info = binance_get_symbol_info(symbol)

    # not 100% sure of the logic below, but I imagine it's possible for the quote asset precision
    # and the step size precision to be different. In this case, to satisfy both filters, we'd need to pick the min
    # asset_rounding_precision = symbol_info['quoteAssetPrecision']

    # the quote precision is not what we need to round by, the stepSize needs to be used instead:
    # https://github.com/sammchardy/python-binance/issues/219
    # {'filterType': 'LOT_SIZE', 'minQty': '0.10000000', 'maxQty': '9000000.00000000', 'stepSize': '0.10000000'},
    step_size = next(Decimal(f["stepSize"]) for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    amount = Decimal(amount)

    # normalize removes trailing zeros, which modifies the precision that quantize uses for rounding
    # https://stackoverflow.com/questions/11227620/drop-trailing-zeros-from-decimal
    return str(amount.quantize(Decimal(step_size).normalize(), rounding=decimal.ROUND_UP))


def binance_normalize_price(amount: t.Union[str, Decimal], symbol: str) -> str:
    symbol_info = binance_get_symbol_info(symbol)

    asset_rounding_precision = symbol_info["quoteAssetPrecision"]

    tick_size = next(f["tickSize"] for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER")
    tick_size_rounding_precision = int(round(-math.log(float(tick_size), 10), 0))

    rounding_precision = min(asset_rounding_precision, tick_size_rounding_precision)

    return format(Decimal(amount), f"0.{rounding_precision}f")


def binance_market_sell(user: User, symbol: str, purchasing_currency: str, amount: Decimal) -> ExchangeOrder:
    # TODO I ran into a case where I needed to subtract a cent to get binance not to fail
    #      this could have been a FPA bug, remove this if it doesn't come up again
    # amount -= 0.01

    sell_pair = symbol + purchasing_currency
    normalized_amount = binance_normalize_price(amount, sell_pair)

    order_params = {
        "symbol": sell_pair,
        "newOrderRespType": "FULL",
        # allows us to purchase crypto in a currency of choice
        # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
        "quoteOrderQty": normalized_amount,
    }

    client = user.binance_client()

    if user.livemode:
        order = client.order_market_sell(**order_params)
    else:
        order = client.create_test_order(**({"side": client.SIDE_SELL, "type": client.ORDER_TYPE_MARKET} | order_params))

    """
    {'clientOrderId': 'nW6LJNE8YF1R0KWVR9r1qU',
    'cummulativeQuoteQty': '84.0000',
    'executedQty': '84.00000000',
    'fills': [{'commission': '0.00020754',
                'commissionAsset': 'BNB',
                'price': '1.0000',
                'qty': '84.00000000',
                'tradeId': 191621}],
    'orderId': 9624122,
    'orderListId': -1,
    'origQty': '84.00000000',
    'price': '0.0000',
    'side': 'SELL',
    'status': 'FILLED',
    'symbol': 'USDCUSD',
    'timeInForce': 'GTC',
    'transactTime': 1626264391365,
    'type': 'MARKET'}
    """

    return ExchangeOrder(
        symbol=symbol,
        trading_pair=sell_pair,
        quantity=order["origQty"],
        # TODO price doesn't mean anything in this context since the order is not filled
        price=order["price"],
        created_at=int(Decimal(order["transactTime"]) / 1000),
        time_in_force=order["timeInForce"],
        type=order["side"],
        id=order["orderId"],
        exchange=SupportedExchanges.BINANCE,
    )


def binance_cancel_order(user: User, order: ExchangeOrder) -> ExchangeOrder:
    client = user.binance_client()

    order_params = {"orderId": order["id"], "symbol": order["trading_pair"]}

    if user.livemode:
        cancelled_order = client.cancel_order(**order_params)
    else:
        # there is no order cancellation in test mode
        log.info("test mode order cancellation")

    """
    {'clientOrderId': 'hash',
    'cummulativeQuoteQty': '0.0000',
    'executedQty': '0.00000000',
    'orderId': 259074455,
    'orderListId': -1,
    'origClientOrderId': 'hash',
    'origQty': '5.10000000',
    'price': '2.0000',
    'side': 'BUY',
    'status': 'CANCELED',
    'symbol': 'ADAUSD',
    'timeInForce': 'GTC',
    'type': 'LIMIT'}
    """

    # TODO should we change the structure of the order at all to note that it is cancelled?

    return order


"""
Binance Order structure:

[{'clientOrderId': 'Egjlu8owfhb0GTnp5auohS',
'cummulativeQuoteQty': '0.0000',
'executedQty': '0.00000000',
'fills': [],
'orderId': 18367859,
'orderListId': -1,
'origQty': '0.24700000',
'price': '56.8830',
'side': 'BUY',
'status': 'NEW',
'symbol': 'ZENUSD',
'timeInForce': 'GTC',
'transactTime': 1628012040277,
'type': 'LIMIT'}]
"""


def binance_market_buy(user: User, symbol: str, purchasing_currency: str, amount: Decimal) -> t.Optional[ExchangeOrder]:
    from binance.exceptions import BinanceAPIException

    client = user.binance_client()
    trading_pair = symbol + purchasing_currency

    order_params = {
        "symbol": trading_pair,
        "newOrderRespType": "FULL",
        # `quoteOrderQty` allows us to purchase crypto in a currency of choice, instead of an amount in the token we are buying
        # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
        "quoteOrderQty": binance_normalize_price(amount, trading_pair),
    }

    log.info("submitting market buy order", order=order_params)

    try:
        if user.livemode:
            binance_order = client.order_market_buy(**order_params)
        else:
            binance_order = client.create_test_order(**({"side": client.SIDE_BUY, "type": client.ORDER_TYPE_MARKET} | order_params))

            # test orders do not generate a valid response hash
            return None
    except BinanceAPIException as e:
        log.error("failed to submit market buy order", error=e)
        return None

    return ExchangeOrder(
        symbol=symbol,
        trading_pair=trading_pair,
        quantity=binance_order["origQty"],
        # TODO price doesn't mean anything in this context since the order is not filled
        price=binance_order["price"],
        created_at=int(Decimal(binance_order["transactTime"]) / 1000),
        time_in_force=OrderTimeInForce(binance_order["timeInForce"]),
        type=OrderType(binance_order["side"]),
        id=binance_order["orderId"],
        exchange=SupportedExchanges.BINANCE,
    )


def binance_limit_buy(user: User, symbol: str, purchasing_currency: str, quantity: Decimal, price: Decimal) -> t.Optional[ExchangeOrder]:
    from binance.exceptions import BinanceAPIException

    client = user.binance_client()
    trading_pair = symbol + purchasing_currency

    order_params = {
        "symbol": trading_pair,
        "newOrderRespType": "FULL",
        # TODO is there a way to specify a number of hours? It seems like only the three standard TIF options are available
        "timeInForce": "GTC",
        "quantity": binance_normalize_purchase_amount(quantity, trading_pair),
        "price": binance_normalize_price(price, trading_pair),
    }

    log.info("submitting limit buy order", order=order_params)

    try:
        if user.livemode:
            binance_order = client.order_limit_buy(**order_params)
        else:
            binance_order = client.create_test_order(**({"side": client.SIDE_BUY, "type": client.ORDER_TYPE_LIMIT} | order_params))

            # test orders do not generate a valid response hash
            return None
    except BinanceAPIException as e:
        log.error("failed to submit limit buy order", error=e)
        return None

    return ExchangeOrder(
        symbol=symbol,
        trading_pair=trading_pair,
        quantity=binance_order["origQty"],
        # TODO price doesn't mean anything in this context since the order is not filled
        price=binance_order["price"],
        created_at=int(Decimal(binance_order["transactTime"]) / 1000),
        time_in_force=OrderTimeInForce(binance_order["timeInForce"]),
        type=OrderType(binance_order["side"]),
        id=binance_order["orderId"],
        exchange=SupportedExchanges.BINANCE,
    )
