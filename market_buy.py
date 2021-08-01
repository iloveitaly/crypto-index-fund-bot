from utils import log
import math
from user import User

from portfolio import add_price_to_portfolio, portfolio_with_allocation_percentages, add_price_to_portfolio, merge_portfolio
from exchanges import binance_portfolio, can_buy_amount_in_exchange, price_of_symbol
from market_cap import coins_with_market_cap
from convert_stablecoins import convert_stablecoins

from data_types import CryptoBalance, CryptoData, MarketBuy
from typing import List

def calculate_market_buy_preferences(target_index: List[CryptoData], current_portfolio: List[CryptoBalance]) -> List[CryptoData]:
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

def purchasing_currency_in_portfolio(user: User, portfolio: List[CryptoBalance]) -> float:
  return math.fsum([
    balance['usd_total']
    for balance in portfolio
    if balance['symbol'] == user.purchasing_currency()
  ])

# TODO pass exchange reference into this method and remove hardcoded binance stuff
def determine_market_buys(
    user: User,
    sorted_buy_preferences: List[CryptoData],
    current_portfolio: List[CryptoBalance],
    target_portfolio: List[CryptoData],
    purchase_balance: float,
  ) -> List[MarketBuy]:
  """
  1. Purchase minimums for each asset
  3. Amount of purchasing currency available
  """

  # binance fees are fixed based on account configuration (BNB amounts, etc) and cannot be pulled dynamically
  # so we don't worry or calculate these as part of our buying preference calculation
  # TODO we'll need to explore if this is different for other exchanges

  # it doesn't look like this is specified in the API, and the minimum is different
  # depending on if you are using the pro vs simple view
  binance_purchase_minimum = 10

  purchase_minimum = user.purchase_min()
  purchase_maximum = user.purchase_max()
  portfolio_total = math.fsum(balance['usd_total'] for balance in current_portfolio)

  if purchase_balance < binance_purchase_minimum:
    log.info("not enough USD to buy anything", purchase_balance=purchase_balance)
    return []

  log.info("enough purchase currency balance", balance=purchase_balance)

  purchase_total = purchase_balance
  purchases = []

  for coin in sorted_buy_preferences:
    target_info = next((target for target in target_portfolio if target['symbol'] == coin['symbol']))

    # TODO consider extracting price calculation logic into a separate method
    purchase_amount = purchase_total if purchase_total < binance_purchase_minimum * 2 else purchase_minimum

    # percentage is not expressed in a < 1 float, so we need to convert it
    target_amount = target_info['percentage'] / 100.0 * portfolio_total

    # make sure purchase total will not overflow the target allocation
    purchase_amount = min(purchase_amount, target_amount, purchase_maximum)

    # we need to at least buy the minimum that the exchange allows
    purchase_amount = max(binance_purchase_minimum, purchase_amount)

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
def make_market_buys(user: User, market_buys: List[MarketBuy]) -> List:
  purchasing_currency = user.purchasing_currency()
  binance_client = user.binance_client()
  orders = []

  # TODO consider executing limit orders based on the current market orders
  #      this could ensure we don't overpay for an asset with low liquidity

  for buy in market_buys:
    # TODO extract this out into a binance specific method

    # symbol is: `baseasset` + `quoteasset`
    purchase_symbol = buy['symbol'] + purchasing_currency
    symbol_info = binance_client.get_symbol_info(purchase_symbol)
    # TODO maybe use Decimal.quantize() to round?
    normalized_amount = round(buy['amount'], symbol_info['quoteAssetPrecision'])

    order_params = {
      'symbol': purchase_symbol,
      'newOrderRespType': 'FULL',
    }

    if user.buy_strategy == 'limit':
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

        difference=str(ask_difference),
        percentage_difference=str(ask_difference / Decimal(lowest_ask) * Decimal(-100.0)),
        bid=highest_bid,
        ask=lowest_ask,
        reported_price=price_of_symbol(buy['symbol'], purchasing_currency)
      )

      # TODO should consider using `Decimal` below instead of `float`

      # TODO can we inspect the order book depth here? Or general liquidity for the market?
      #      what else can we do to improve our purchase strategy?

      # the quote precision is not what we need to round by, the stepSize needs to be used instead:
      # https://github.com/sammchardy/python-binance/issues/219
      step_size = next(f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
      precision_from_step_size = int(round(-math.log(float(step_size), 10), 0))

      # TODO add option to use the midpoint, or some other position, of the order book instead of the lowest ask

      order_params |= {
        # TODO is there a way to specify a number of hours? It seems like only the three standard TIF options are available
        'timeInForce': 'GTC',
        'quantity': round(normalized_amount / float(highest_bid), precision_from_step_size),
        'price': highest_bid
      }
    else: # market
      order_params |= {
        # `quoteOrderQty` allows us to purchase crypto in a currency of choice, instead of an amount in the token we are buying
        # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
        'quoteOrderQty': normalized_amount,
      }

    log.info("submitting market buy order", order=order_params)

    from binance.exceptions import BinanceAPIException

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

  return orders
