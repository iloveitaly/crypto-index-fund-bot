import functools
import math
import typing as t
from decimal import Decimal

from binance.client import Client as BinanceClient

from .. import utils
from ..data_types import CryptoBalance, ExchangeOrder, SupportedExchanges
from ..user import User

# https://algotrading101.com/learn/binance-python-api-guide/
# https://github.com/timggraf/crypto-index-bot seems to have details about binance errors. Need to handle more error types


# initializing a new client actually hits the `ping` endpoint on the API
# which is on of the reasons we want to cache it
@functools.cache
def public_binance_client() -> BinanceClient:
    return BinanceClient("", "", tld="us")


def binance_purchase_minimum() -> Decimal:
    return Decimal(10)


def binance_portfolio(user: User) -> t.List[CryptoBalance]:
    account = user.binance_client().get_account()

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
            quantity=Decimal(order["origQty"]),
            price=Decimal(order["price"]),
            # binance represents time in milliseconds
            created_at=int(Decimal(order["time"]) / 1000),
            time_in_force=order["timeInForce"],
            type=order["side"],
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
    step_size = next(f["stepSize"] for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size_rounding_precision = int(round(-math.log(float(step_size), 10), 0))

    # rounding_precision = min(asset_rounding_precision, step_size_rounding_precision)
    rounding_precision = step_size_rounding_precision
    return format(Decimal(amount), f"0.{rounding_precision}f")


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
        order = client.create_test_order(**({"side": client.SIDE_SELL} | order_params))

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
        symbol=sell_pair,
        quantity=order["origQty"],
        # TODO price doesn't mean anything in this context since the order is not filled
        price=order["price"],
        created_at=int(Decimal(order["time"]) / 1000),
        time_in_force=order["timeInForce"],
        type=order["side"],
        id=order["orderId"],
        exchange=SupportedExchanges.BINANCE,
    )
