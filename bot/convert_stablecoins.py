import typing as t

from . import exchanges
from .data_types import CryptoBalance, SupportedExchanges
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

    orders = []
    exchange_purchase_min = exchanges.purchase_minimum(exchange)

    stablecoin_portfolio = [balance for balance in portfolio if balance["symbol"] in stablecoin_symbols]

    for balance in stablecoin_portfolio:
        amount = balance["amount"]
        symbol = balance["symbol"]

        if amount < exchange_purchase_min:
            log.info("cannot convert stablecoin, not above minimum", min=exchange_purchase_min, symbol=symbol, amount=amount)
            continue

        log.info("converting stablecoins", symbol=symbol, amount=amount)

        order = exchanges.market_sell(exchange=exchange, user=user, symbol=symbol, amount=amount, purchasing_currency=purchasing_currency)

        orders.append(order)

    return orders
