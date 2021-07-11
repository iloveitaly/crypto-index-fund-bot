from utils import log
from user import User

from portfolio import add_price_to_portfolio, portfolio_with_allocation_percentages, add_price_to_portfolio, merge_portfolio
from exchanges import binance_portfolio
from market_cap import coins_with_market_cap

from data_types import CryptoBalance, CryptoData, MarketBuy
from typing import List

def calculate_market_buy_preferences(target_index: List[CryptoData], current_portfolio: List[CryptoBalance]) -> List[CryptoData]:
  """
  Buying priority:

  1. Buying what's unique to this exchange
  2. Buying something new, as opposed to getting closer to a new allocation
  3. Buying whatever has dropped the most
  4. Buying what has the most % delta from the target
  """

  log.info('calculating market buy preferences', target_index=len(target_index), current_portfolio=len(current_portfolio))

  sorted_by_largest_target_delta = sorted(
    target_index,
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

def determine_market_buys(user: User, sorted_buy_preferences: List[CryptoData], current_portfolio: List[CryptoBalance], target_portfolio: List[CryptoData]) -> List[MarketBuy]:
  """
  1. Purchase minimums for each asset
  3. Amount of purchasing currency available
  """

  # it doesn't look like this is specified in the API, and the minimum is different
  # depending on if you are using the pro vs simple view
  binance_purchase_minimum = 10

  purchase_minimum = user.purchase_min()
  purchase_maximum = user.purchase_max()

  import math
  portfolio_total = math.fsum(balance['usd_total'] for balance in current_portfolio)

  purchase_balance = next((
    balance
    for balance in current_portfolio
    # TODO should make this dynamic
    if balance['symbol'] == 'USD'
  ), None)

  # for testing arbitrary amounts
  # purchase_balance = { "usd_total": 50 }

  if purchase_balance is None or purchase_balance['usd_total'] < binance_purchase_minimum:
    log.info("not enough USD to buy anything", purchase_balance=purchase_balance)
    return []

  purchase_total = purchase_balance['usd_total']
  purchase_slots = max(1, round(purchase_total / purchase_minimum, 0))
  purchases = []

  for coin in sorted_buy_preferences:
    # TODO are there token-specific buy minimums?

    # TODO consider extracting price calculation logic into a separate method
    purchase_amount = purchase_total if purchase_slots == 1 else purchase_minimum

    target_info = next((target for target in target_portfolio if target['symbol'] == coin['symbol']))
    # percentage is not expressed in a < 1 float, so we need to convert it
    target_amount = target_info['percentage'] / 100.0 * portfolio_total

    # make sure purchase total will not overflow the target allocation
    purchase_amount = min(purchase_amount, target_amount, purchase_maximum)

    purchases.append({
      'symbol': coin['symbol'],

      # amount in purchasing currency, not a quantity of the symbol to purchase
      'amount': purchase_amount
    })

    purchase_total -= purchase_amount
    purchase_slots -= 1

    if purchase_slots == 0:
      break

  # binance fees are fixed based on account configuration (BNB amounts, etc) and cannot be pulled dynamically
  # so we don't worry or calculate these as part of our buying preference calculation

  return purchases

# https://www.binance.us/en/usercenter/wallet/money-log
def make_market_buys(user: User, market_buys: List[MarketBuy]) -> List:
  purchasing_currency = user.purchasing_currency()
  binance_client = user.binance_client()
  orders = []

  # TODO consider executing limit orders based on the current market orders
  #      this could ensure we don't overpay for an asset with low liquidity

  for buy in market_buys:
    order_params = {
      # symbol is: `baseasset` + `quoteasset`
      'symbol': buy['symbol'] + purchasing_currency,
      'newOrderRespType': 'FULL',

      # allows us to purchase crypto in a currency of choice
      # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
      'quoteOrderQty': buy['amount'],
      # quantity=float(quantity)
    }

    if user.livemode:
      order = binance_client.order_market_buy(**order_params)
      # binance.exceptions.BinanceAPIException: APIError(code=-1111): Precision is over the maximum defined for this asset.
    else:
      from binance.client import Client

      # if test is successful, order will be an empty dict
      order = binance_client.create_test_order(**({
        'side': Client.SIDE_BUY,
        'type': Client.ORDER_TYPE_MARKET,
      } | order_params))

    orders.append(order)

  return orders

# run directly to output list of buys that would be made
if __name__ == "__main__":
  from user import user_from_env
  from exchanges import binance_portfolio

  user = user_from_env()
  portfolio_target = coins_with_market_cap(user)

  external_portfolio = user.external_portfolio
  external_portfolio = add_price_to_portfolio(external_portfolio, user.purchasing_currency())

  current_portfolio = binance_portfolio(user)
  current_portfolio = merge_portfolio(current_portfolio, external_portfolio)
  current_portfolio = add_price_to_portfolio(current_portfolio, user.purchasing_currency())
  current_portfolio = portfolio_with_allocation_percentages(current_portfolio)

  sorted_market_buys = calculate_market_buy_preferences(portfolio_target, current_portfolio)
  market_buys = determine_market_buys(user, sorted_market_buys, current_portfolio, portfolio_target)

  from utils import table_output
  table_output(market_buys)

  # TODO add option to actually make market purchases
  orders = make_market_buys(user, market_buys)

  # TODO inspect order response structure and extract important information for the logs

