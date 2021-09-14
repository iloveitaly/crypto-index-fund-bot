import datetime
import typing as t

from bot.data_types import OrderTimeInForce, SupportedExchanges, OrderType

from . import exchanges
from .user import User, user_from_env
from .utils import log


def cancel_stale_open_orders(user: User, exchange: SupportedExchanges) -> t.List:
    order_time_limit = user.stale_order_hour_limit

    old_orders = [
        order
        for order in exchanges.open_orders(exchange, user)
        if order["type"] == OrderType.BUY
        and order["time_in_force"] == OrderTimeInForce.GTC
        and order["created_at"] < (datetime.datetime.now() - datetime.timedelta(hours=order_time_limit)).timestamp()
    ]

    if not old_orders:
        log.info("no stale open orders")
        return []

    cancelled_orders = []

    for order in old_orders:
        log.info("cancelling order", order=order)
        cancelled_orders.append(exchanges.cancel_order(exchange, user, order))

    return cancelled_orders


if __name__ == "__main__":
    user = user_from_env()

    if user.cancel_stale_orders:
        for exchange in user.exchanges:
            cancel_stale_open_orders(user, exchange)
