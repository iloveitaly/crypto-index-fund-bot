import datetime
import typing as t

from user import User, user_from_env
from utils import log
from binance.client import Client as BINANCE_CONSTANTS

# TODO abstract out binance specifics
def cancel_stale_open_orders(user: User) -> t.List:
  binance_client = user.binance_client()
  order_time_limit = user.stale_order_hour_limit

  old_orders = [
    order
    for order in binance_client.get_open_orders()
    if order['side'] == BINANCE_CONSTANTS.SIDE_BUY and order['timeInForce'] == BINANCE_CONSTANTS.TIME_IN_FORCE_GTC and
    # `time` from binance is expressed in milliseconds
    order['time'] < (datetime.datetime.now() - datetime.timedelta(hours=order_time_limit)).timestamp() * 1000.0
  ]

  if not old_orders:
    log.info('no stale open orders')
    return []

  cancelled_orders = []

  for order in old_orders:
    log.info('cancelling order', order=order)
    cancelled_orders.append(binance_client.cancel_order(symbol=order['symbol'], orderId=order['orderId']))

  return cancelled_orders

if __name__ == '__main__':
  cancel_stale_open_orders(user_from_env())