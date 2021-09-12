from bot.data_types import CryptoBalance, SupportedExchanges
import typing as t

from . import exchanges
from .user import User
from .utils import log


# convert all stablecoins of the purchasing currency into the purchasing currency so we can use it
# in binance, you need to purchase in USD and cannot purchase most currencies from a stablecoin
def convert_stablecoins(user: User, exchange: SupportedExchanges, portfolio: t.List[CryptoBalance]) -> t.List[t.Dict]:
    purchasing_currency = user.purchasing_currency
    stablecoin_symbols = []

    # TODO check if currency is a stablecoin?

    if purchasing_currency == "USD":
        stablecoin_symbols = ["USDC", "USDT", "BUSD"]
    else:
        raise Exception("unexpected purchasing currency input")

    binance_client = user.binance_client()
    orders = []
    exchange_purchase_min = exchanges.purchase_minimum(exchange)

    stablecoin_portfolio = [balance for balance in portfolio if balance["symbol"] in stablecoin_symbols]

    for balance in stablecoin_portfolio:
        purchase_symbol = balance["symbol"] + "USD"
        amount = balance["amount"]

        if amount < exchange_purchase_min:
            log.info("cannot convert stablecoin, not above minimum", min=exchange_purchase_min, symbol=purchase_symbol, amount=amount)
            continue

        # TODO I ran into a case where I needed to subtract a cent to get binance not to fail
        #      this could have been a FPA bug, remove this if it doesn't come up again
        # amount -= 0.01

        normalized_amount = exchanges.binance_normalize_price(amount, purchase_symbol)

        log.info("converting stablecoins", symbol=purchase_symbol, amount=amount, normalized_amount=normalized_amount)

        # TODO binance order construction should be pulled out into a separate method

        order_params = {
            "symbol": purchase_symbol,
            "newOrderRespType": "FULL",
            # allows us to purchase crypto in a currency of choice
            # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
            "quoteOrderQty": normalized_amount,
        }

        # TODO respect livemode flag by creating a common method for executing binance orders

        order = binance_client.order_market_sell(**order_params)

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

        log.info("order completed", order_id=order["orderId"], symbol=order["symbol"])

        orders.append(order)

    return orders
