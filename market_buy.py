from utils import log
import math
from user import User

from portfolio import add_price_to_portfolio, portfolio_with_allocation_percentages, add_price_to_portfolio, merge_portfolio
from exchanges import binance_portfolio, can_buy_amount_in_exchange
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
    normalized_amount = round(buy['amount'], symbol_info['quoteAssetPrecision'])

    order_params = {
      'symbol': purchase_symbol,
      'newOrderRespType': 'FULL',

      # allows us to purchase crypto in a currency of choice
      # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
      'quoteOrderQty': normalized_amount,
      # quantity=float(quantity)
    }

    log.info("submitting market buy order", symbol=purchase_symbol, amount=normalized_amount)

    from binance.exceptions import BinanceAPIException

    if user.livemode:
      order = binance_client.order_market_buy(**order_params)
      # binance.exceptions.BinanceAPIException: APIError(code=-2010): Account has insufficient balance for requested action.
      # binance.exceptions.BinanceAPIException: APIError(code=-1111): Precision is over the maximum defined for this asset.
      # binance.exceptions.BinanceAPIException: APIError(code=-1013): Filter failure: MIN_NOTIONAL
      # Account has insufficient balance for requested action.
    else:
      from binance.client import Client
      # if test is successful, order will be an empty dict
      order = binance_client.create_test_order(**({
        'side': Client.SIDE_BUY,
        'type': Client.ORDER_TYPE_MARKET,
      } | order_params))

    orders.append(order)


  return orders
