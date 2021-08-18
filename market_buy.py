from utils import log
from user import User

import math
from exchanges import binance_open_orders, binance_normalize_purchase_amount, binance_purchase_minimum, can_buy_amount_in_exchange, price_of_symbol, binance_normalize_price

from data_types import CryptoBalance, CryptoData, MarketBuy, MarketBuyStrategy
import typing as t

def calculate_market_buy_preferences(target_index: t.List[CryptoData], current_portfolio: t.List[CryptoBalance]) -> t.List[CryptoData]:
  """
  Buying priority:

  1. Buying what's unique to this exchange
  2. Buying something new, as opposed to getting closer to a new allocation
  3. Buying whatever has dropped the most
  4. Buying what has the most % delta from the target

  Filter out coins that have exceeded their targets
  """

  filtered_coins_exceeding_target = []
  for coin_data in target_index:
    current_percentage = next((
      balance['percentage']
      for balance in current_portfolio
      if balance['symbol'] == coin_data['symbol']
    ), 0)

    if current_percentage < coin_data['percentage']:
      filtered_coins_exceeding_target.append(coin_data)
    else:
      log.info("coin exceeding target", symbol=coin_data['symbol'], percentage=current_percentage, target=coin_data['percentage'])


  log.info('calculating market buy preferences', target_index=len(target_index), current_portfolio=len(current_portfolio))

  sorted_by_largest_target_delta = sorted(
    filtered_coins_exceeding_target,
    # TODO fsum for math?
    key=lambda coin_data: next((balance['percentage'] for balance in current_portfolio if balance['symbol'] == coin_data['symbol']), 0) - coin_data['percentage']
  )

  # TODO think about grouping drops into tranches so the above sort isn't completely useless
  sorted_by_largest_recent_drop = sorted(
    sorted_by_largest_target_delta,
    key=lambda coin_data: coin_data['30d_change']
  )

  symbols_in_current_allocation = [item['symbol'] for item in current_portfolio]
  index_by_unowned_assets = sorted(
    sorted_by_largest_recent_drop,
    key=lambda coin_data: 1 if coin_data['symbol'] in symbols_in_current_allocation else 0
  )

  # TODO how should we deal with multiple exchanges here?

  return index_by_unowned_assets

def purchasing_currency_in_portfolio(user: User, portfolio: t.List[CryptoBalance]) -> float:
  # ideally, we wouldn't need to have a reserve amount. However, FP math is challenging and it's easy
  # to be off a cent or two. It's easier just to reserve $1 and not deal with it. Especially for a fun project.
  reserve_amount = 1

  # TODO we should use Decimal here instead of float
  total = math.fsum([
    balance['usd_total']
    for balance in portfolio
    if balance['symbol'] == user.purchasing_currency
  ])

  return max(total - reserve_amount, 0)

# TODO pass exchange reference into this method and remove hardcoded binance stuff
def determine_market_buys(
    user: User,
    sorted_buy_preferences: t.List[CryptoData],
    current_portfolio: t.List[CryptoBalance],
    target_portfolio: t.List[CryptoData],
    purchase_balance: float,
  ) -> t.List[MarketBuy]:
  """
  1. Is the asset currently trading?
  2. Do we have the minimum purchase amount?
  3. Are there open orders for the asset already?
  """

  # binance fees are fixed based on account configuration (BNB amounts, etc) and cannot be pulled dynamically
  # so we don't worry or calculate these as part of our buying preference calculation
  # TODO we'll need to explore if this is different for other exchanges

  # it doesn't look like this is specified in the API, and the minimum is different
  # depending on if you are using the pro vs simple view
  exchange_purchase_minimum = binance_purchase_minimum()

  user_purchase_minimum = user.purchase_min
  user_purchase_maximum = user.purchase_max
  portfolio_total = math.fsum(balance['usd_total'] for balance in current_portfolio)

  if purchase_balance < exchange_purchase_minimum:
    log.info("not enough USD to buy anything", purchase_balance=purchase_balance)
    return []

  log.info("enough purchase currency balance", balance=purchase_balance)

  purchase_total = purchase_balance
  purchases = []

  existing_orders = binance_open_orders(user)
  symbols_of_existing_orders = [order['symbol'] for order in existing_orders]

  for coin in sorted_buy_preferences:
    # TODO may make sense in the future to check the purchase amount and adjust the expected
    if coin['symbol'] in symbols_of_existing_orders:
      log.info("already have an open order for this coin", coin=coin)
      continue

    # round up the purchase amount to the total available balance if we don't have enough to buy two tokens
    purchase_amount = purchase_total if purchase_total < exchange_purchase_minimum * 2 else purchase_minimum

    # percentage is not expressed in a < 1 float, so we need to convert it
    coin_portfolio_info = next((target for target in target_portfolio if target['symbol'] == coin['symbol']))
    target_amount = coin_portfolio_info['percentage'] / 100.0 * portfolio_total

    # make sure purchase total will not overflow the target allocation
    purchase_amount = min(purchase_amount, target_amount, purchase_maximum)

    # we need to at least buy the minimum that the exchange allows
    purchase_amount = max(exchange_purchase_minimum, purchase_amount)

    if purchase_amount > purchase_total:
      log.info("not enough purchase currency balance for coin", balance=purchase_total, coin=coin['symbol'])
      continue

    paired_symbol = coin['symbol'] + user.purchasing_currency()
    if not can_buy_amount_in_exchange(paired_symbol, purchase_amount):
      # above method will log a warning
      continue

    purchases.append({
      'symbol': coin['symbol'],

      # TODO should we include the paired symbol in this data structure?

      # amount in purchasing currency, not a quantity of the symbol to purchase
      'amount': purchase_amount
    })

    purchase_total -= purchase_amount

    if purchase_total <= 0:
      break

  return purchases

# https://www.binance.us/en/usercenter/wallet/money-log
def make_market_buys(user: User, market_buys: t.List[MarketBuy]) -> t.List:
  purchasing_currency = user.purchasing_currency
  binance_client = user.binance_client()
  orders = []

  # TODO consider executing limit orders based on the current market orders
  #      this could ensure we don't overpay for an asset with low liquidity

  for buy in market_buys:
    # TODO extract this out into a binance specific method

    # symbol is: `baseasset` + `quoteasset`
    purchase_symbol = buy['symbol'] + purchasing_currency
    normalized_amount = binance_normalize_purchase_amount(buy['amount'], purchase_symbol)

    order_params = {
      'symbol': purchase_symbol,
      'newOrderRespType': 'FULL',
    }

    if user.buy_strategy == MarketBuyStrategy.LIMIT:
      # order depth returns the lowest asks and the highest bids
      # increasing limits returns lower bids and higher asks
      # grab a long-ish order book to get some analytics on the order book

      order_book = binance_client.get_order_book(symbol=purchase_symbol, limit=100)

      # price that binance reports is at the bottom of the order book
      # looks like they use the bottom of the ask stack to clear market orders (makes sense)
      lowest_ask = order_book['asks'][0][0]
      highest_bid = order_book['bids'][0][0]

      from decimal import Decimal
      ask_difference = Decimal(highest_bid) - Decimal(lowest_ask)

      log.info(
        "price analytics",

        symbol=purchase_symbol,
        difference=str(ask_difference),
        percentage_difference=str(ask_difference / Decimal(lowest_ask) * Decimal(-100.0)),
        bid=highest_bid,
        ask=lowest_ask,
        reported_price=price_of_symbol(buy['symbol'], purchasing_currency)
      )

      # TODO pull percentage drop attempt from user model
      limit_price = min(Decimal(highest_bid), Decimal(lowest_ask) * Decimal(0.95))
      order_quantity = Decimal(normalized_amount) / limit_price

      # TODO can we inspect the order book depth here? Or general liquidity for the market?
      #      what else can we do to improve our purchase strategy?

      # TODO add option to use the midpoint, or some other position, of the order book instead of the lowest ask

      order_params |= {
        # TODO is there a way to specify a number of hours? It seems like only the three standard TIF options are available
        'timeInForce': 'GTC',
        'quantity': binance_normalize_purchase_amount(order_quantity, purchase_symbol),
        'price': binance_normalize_price(limit_price, purchase_symbol),
      }

      log.info("submitting limit buy order", order=order_params)
    else: # market
      order_params |= {
        # `quoteOrderQty` allows us to purchase crypto in a currency of choice, instead of an amount in the token we are buying
        # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
        'quoteOrderQty': normalized_amount,
      }

      log.info("submitting market buy order", order=order_params)

    from binance.exceptions import BinanceAPIException

    """
    Order structure:

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

    try:
      if user.livemode:
        if user.buy_strategy == 'limit':
          order = binance_client.order_limit_buy(**order_params)
        else:
          order = binance_client.order_market_buy(**order_params)
      else:
        from binance.client import Client

        # if test is successful, order will be an empty dict
        order = binance_client.create_test_order(**({
          'side': Client.SIDE_BUY,
          'type': Client.ORDER_TYPE_LIMIT if user.buy_strategy == 'limit' else Client.ORDER_TYPE_MARKET,
        } | order_params))

      orders.append(order)
    except BinanceAPIException as e:
      log.error("failed to submit market buy order", error=e)

  return orders
