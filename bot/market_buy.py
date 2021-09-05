from .utils import log
from .user import User

import math
from . import exchanges

from .data_types import CryptoBalance, CryptoData, MarketBuy, MarketBuyStrategy
import typing as t

def calculate_market_buy_preferences(
  target_index: t.List[CryptoData],
  current_portfolio: t.List[CryptoBalance],
  deprioritized_coins: t.List[str],
) -> t.List[CryptoData]:

  """
  Buying priority:

  1. Buying what hasn't be deprioritized by the user
  2. Buying what has > 1% of the market cap
  3. Buying what's unique to this exchange
  4. Buying something new, as opposed to getting closer to a new allocation
  5. Buying whatever has dropped the most
  6. Buying what has the most % delta from the target

  Filter out coins that have exceeded their targets
  """

  log.info('calculating market buy preferences',
    target_index=len(target_index),
    current_portfolio=len(current_portfolio)
  )

  coins_below_index_target = []

  # first, let's exclude all coins that we've exceeded target on
  for coin_data in target_index:
    current_percentage = next((
      balance['percentage']
      for balance in current_portfolio
      if balance['symbol'] == coin_data['symbol']
    ), 0)

    if current_percentage < coin_data['percentage']:
      coins_below_index_target.append(coin_data)
    else:
      log.debug("coin exceeding target, skipping", symbol=coin_data['symbol'], percentage=current_percentage, target=coin_data['percentage'])

  sorted_by_largest_target_delta = sorted(
    coins_below_index_target,
    # TODO fsum for math?
    key=lambda coin_data: next((
      balance['percentage']
      for balance in current_portfolio
      if balance['symbol'] == coin_data['symbol']
    ), 0) - coin_data['percentage']
  )

  # TODO think about grouping drops into tranches so the above sort isn't completely useless
  sorted_by_largest_recent_drop = sorted(
    sorted_by_largest_target_delta,
    key=lambda coin_data: coin_data['30d_change']
  )

  # prioritize tokens we don't own yet
  symbols_in_current_allocation = [item['symbol'] for item in current_portfolio]
  sorted_by_unowned_coins = sorted(
    sorted_by_largest_recent_drop,
    key=lambda coin_data: 1 if coin_data['symbol'] in symbols_in_current_allocation else 0
  )

  # prioritize tokens that make up > 1% of the market
  # and either (a) we don't own or (b) our target allocation is off by a factor of 6
  # why 6? It felt right based on looking at what I wanted out of my current allocation

  def should_token_be_treated_as_unowned(coin_data: CryptoData) -> int:
    if coin_data['percentage'] < 1:
      return 1

    current_percentage = next((
      balance['percentage']
      for balance in current_portfolio
      if balance['symbol'] == coin_data['symbol']
    ), 0)

    if current_percentage == 0:
      return 0

    current_allocation_delta = coin_data['percentage'] / current_percentage

    if current_allocation_delta > 6:
      return 0
    else:
      return 1

  sorted_by_large_market_cap_coins = sorted(
    sorted_by_unowned_coins,
    key=should_token_be_treated_as_unowned
  )

  # last, but not least, let's respect the user's preference for deprioritizing coins
  sorted_by_deprioritized_coins = sorted(
    sorted_by_large_market_cap_coins,
    key=lambda coin_data: 1 if coin_data['symbol'] in deprioritized_coins else 0
  )

  return sorted_by_deprioritized_coins

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
  # depending on if you are using the pro vs simple view. This is the purchasing minimum on binance
  # but not on
  exchange_purchase_minimum = exchanges.binance_purchase_minimum()

  user_purchase_minimum = user.purchase_min
  user_purchase_maximum = user.purchase_max
  portfolio_total = math.fsum(balance['usd_total'] for balance in current_portfolio)

  if purchase_balance < exchange_purchase_minimum:
    log.info("not enough USD to buy anything", purchase_balance=purchase_balance)
    return []

  log.info("enough purchase currency balance",
    balance=purchase_balance,
    exchange_minimum=exchange_purchase_minimum,
    user_minimum=user_purchase_minimum,
  )

  purchase_total = purchase_balance
  purchases = []

  existing_orders = exchanges.binance_open_orders(user)
  symbols_of_existing_orders = [order['symbol'] for order in existing_orders]

  for coin in sorted_buy_preferences:
    # TODO may make sense in the future to check the purchase amount and adjust the expected
    if coin['symbol'] in symbols_of_existing_orders:
      # TODO add current order information to logs
      log.info("already have an open order for this coin", coin=coin)
      continue

    paired_symbol = coin['symbol'] + user.purchasing_currency
    if not exchanges.can_buy_amount_in_exchange(paired_symbol):
      continue

    # round up the purchase amount to the total available balance if we don't have enough to buy two tokens
    purchase_amount = purchase_total if purchase_total < exchange_purchase_minimum * 2 else user_purchase_minimum

    # percentage is not expressed in a < 1 float, so we need to convert it
    coin_portfolio_info = next((target for target in target_portfolio if target['symbol'] == coin['symbol']))
    target_amount = coin_portfolio_info['percentage'] / 100.0 * portfolio_total

    # make sure purchase total will not overflow the target allocation
    purchase_amount = min(purchase_amount, target_amount, user_purchase_maximum)

    # make sure the floor purchase amount is at least the user-specific minimum
    purchase_amount = max(purchase_amount, user_purchase_minimum)

    # we need to at least buy the minimum that the exchange allows
    purchase_amount = max(exchange_purchase_minimum, purchase_amount)

    # TODO right now the minNotional filter is NOT respected since the user min is $30, which is normally higher than this value
    #      this is something we'll have to handle properly in the future
    # minimum_token_quantity_in_exchange(paired_symbol)
    # symbol_info = public_binance_client.get_symbol_info(paired_symbol)
    # tick_size = next(f['minNotional'] for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')

    if purchase_amount > purchase_total:
      log.info("not enough purchase currency balance for coin", amount=purchase_amount, balance=purchase_total, coin=coin['symbol'])
      continue

    log.info("adding purchase preference", symbol=coin['symbol'], amount=purchase_amount)

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
  if not market_buys:
    return []

  purchasing_currency = user.purchasing_currency
  binance_client = user.binance_client()
  orders = []

  # TODO consider executing limit orders based on the current market orders
  #      this could ensure we don't overpay for an asset with low liquidity

  for buy in market_buys:
    # TODO extract this out into a binance specific method

    # symbol is: `baseasset` + `quoteasset`
    purchase_symbol = buy['symbol'] + purchasing_currency

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
        reported_price=exchanges.price_of_symbol(buy['symbol'], purchasing_currency)
      )

      # TODO calculate momentum, or low price over last 24hrs, to determine the ideal drop price
      # TODO pull percentage drop attempt from user model
      limit_price = min(Decimal(highest_bid), Decimal(lowest_ask) * Decimal(0.97))
      limit_price = min(exchanges.low_over_last_day(purchase_symbol), limit_price)
      order_quantity = Decimal(buy['amount']) / limit_price

      # TODO can we inspect the order book depth here? Or general liquidity for the market?
      #      what else can we do to improve our purchase strategy?

      # TODO add option to use the midpoint, or some other position, of the order book instead of the lowest ask

      order_params |= {
        # TODO is there a way to specify a number of hours? It seems like only the three standard TIF options are available
        'timeInForce': 'GTC',
        'quantity': exchanges.binance_normalize_purchase_amount(order_quantity, purchase_symbol),
        'price': exchanges.binance_normalize_price(limit_price, purchase_symbol),
      }

      log.info("submitting limit buy order", order=order_params)
    else: # market
      order_params |= {
        # `quoteOrderQty` allows us to purchase crypto in a currency of choice, instead of an amount in the token we are buying
        # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
        'quoteOrderQty': exchanges.binance_normalize_price(buy['amount'], purchase_symbol),
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
        if user.buy_strategy == MarketBuyStrategy.LIMIT:
          order = binance_client.order_limit_buy(**order_params)
        else:
          order = binance_client.order_market_buy(**order_params)
      else:
        from binance.client import Client

        # if test is successful, order will be an empty dict
        order = binance_client.create_test_order(**({
          'side': Client.SIDE_BUY,
          'type': Client.ORDER_TYPE_LIMIT if user.buy_strategy == MarketBuyStrategy.LIMIT else Client.ORDER_TYPE_MARKET,
        } | order_params))

      log.info("order successfully completed", order=order)

      orders.append(order)
    except BinanceAPIException as e:
      log.error("failed to submit market buy order", error=e)

  # in testmode, the result is an empty dict
  # remove this since it doesn't provide any useful information and is confusing to parse downstream
  return list(filter(None, orders))
