from bot.data_types import SupportedExchanges
import datetime
import typing as t

from binance.client import Client as BINANCE_CONSTANTS

from .user import User, user_from_env
from .utils import log
from . import exchanges


# TODO abstract out binance specifics
def cancel_stale_open_orders(user: User, exchange: SupportedExchanges) -> t.List:
    binance_client = user.binance_client()
    order_time_limit = user.stale_order_hour_limit

    old_orders = [
        order
        for order in exchanges.open_orders(exchange, user)
        if order["type"] == BINANCE_CONSTANTS.SIDE_BUY and order["time_in_force"] == BINANCE_CONSTANTS.TIME_IN_FORCE_GTC and
        # `time` from binance is expressed in milliseconds
        order["created_at"] < (datetime.datetime.now() - datetime.timedelta(hours=order_time_limit)).timestamp()
    ]

    if not old_orders:
        log.info("no stale open orders")
        return []

    cancelled_orders = []

    for order in old_orders:
        log.info("cancelling order", order=order)
        cancelled_orders.append(binance_client.cancel_order(symbol=order["symbol"], orderId=order["orderId"]))

    return cancelled_orders


if __name__ == "__main__":
    user = user_from_env()
    for exchange in user.exchanges:
        cancel_stale_open_orders(user, exchange)
