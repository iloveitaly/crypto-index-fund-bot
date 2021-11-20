import time
import typing as t
from decimal import Decimal

from . import exchanges
from .data_types import CryptoBalance, SupportedExchanges
from .user import User
from .utils import log


def wait_until_orders_cleared(user: User, orders) -> None:
    client = user.binance_client()

    for i in range(5):
        latest_orders = [client.get_order(orderId=order["id"], symbol=order["trading_pair"]) for order in orders]

        if all([order["status"] == client.ORDER_STATUS_FILLED for order in latest_orders]):
            break

        log.info("waiting for orders to clear", attempt=i)
        time.sleep(i ** i)


# TODO is this required across all exchanges? Or is this just a binance thing?
def convert_stablecoins(user: User, exchange: SupportedExchanges, portfolio: t.List[CryptoBalance]) -> t.List[t.Dict]:
    """
    convert all stablecoins of the purchasing currency into the purchasing currency so we can use it
    in binance, you need to purchase in USD and cannot purchase most currencies from a stablecoin
    """
    purchasing_currency = user.purchasing_currency
    stablecoin_symbols = []

    # TODO check if currency is a stablecoin? Can we do this programmatically?

    if purchasing_currency == "USD":
        stablecoin_symbols = ["USDC", "USDT", "BUSD"]
    else:
        raise Exception("unexpected purchasing currency input")

    orders = []
    exchange_purchase_min = exchanges.purchase_minimum(exchange)

    stablecoin_portfolio = [balance for balance in portfolio if balance["symbol"] in stablecoin_symbols]

    for balance in stablecoin_portfolio:
        # TODO dynamically calculate the holdback based on the exchange definition
        # in some cases, but not all, binance requires that a small % is held back
        amount = balance["amount"] * Decimal("0.999")
        symbol = balance["symbol"]

        if amount < exchange_purchase_min:
            log.info("cannot convert stablecoin, not above minimum", min=exchange_purchase_min, symbol=symbol, amount=amount)
            continue

        log.info("converting stablecoins", symbol=symbol, amount=amount)

        order = exchanges.market_sell(exchange=exchange, user=user, symbol=symbol, amount=amount, purchasing_currency=purchasing_currency)
        orders.append(order)

    wait_until_orders_cleared(user, orders)

    # TODO convert to ExchangeOrder

    return orders
