from .data_types import CryptoData, CryptoBalance
import typing as t

from .user import User
from .utils import log

from decimal import Decimal
import math

# https://python-binance.readthedocs.io/en/latest/market_data.html
# https://binance-docs.github.io/apidocs/spot/en/#change-log
# https://github.com/binance-us/binance-official-api-docs
# https://dev.binance.vision/
from binance.client import Client as BinanceClient
public_binance_client = BinanceClient('', '', tld='us')
binance_exchange = public_binance_client.get_exchange_info()

# `symbol` is a trading pair
# this includes both USDT and USD prices
# the pair formatting is 'BTCUSD'
binance_prices = {
  price_dict['symbol']: float(price_dict['price'])
  # `get_all_tickers` is only called once
  for price_dict in public_binance_client.get_all_tickers()
}

def can_buy_amount_in_exchange(symbol: str):
  binance_symbol_info = public_binance_client.get_symbol_info(symbol)

  if binance_symbol_info is None:
    log.warn("symbol did not return any data", symbol=symbol)
    return False

  # the min notional amount specified on the symbol data is the min in USD
  # that needs to be purchased. Most of the time, the minimum is enforced by
  # the binance-wide minimum, but this is not always the case.

  if binance_symbol_info['status'] != 'TRADING':
    log.info("symbol is not trading, skipping", symbol=symbol)
    return False

  return True


def can_buy_in_exchange(exchange, symbol, purchasing_currency):
  mapping = {
    'binance': can_buy_in_binance,
    'coinbase': can_buy_in_coinbase
  }

  return mapping[exchange](symbol, purchasing_currency)

def can_buy_in_binance(symbol, purchasing_currency):
  for coin in binance_exchange['symbols']:
    # in the binance UI, you can buy BNB with USD, but
    if coin['baseAsset'] == symbol and coin['quoteAsset'] == purchasing_currency:
      return True

  return False

# https://docs.pro.coinbase.com/#client-libraries
import coinbasepro as cbpro
coinbase_public_client = cbpro.PublicClient()
coinbase_exchange = coinbase_public_client.get_products()

def low_over_last_day(purchasing_symbol: str) -> Decimal:
  import datetime

  # TODO coinbase option is below, but ran into some issues with it that I can't remember
  # candles = coinbase_public_client.get_product_historic_rates(
  #   product_id="PAXG-USD",
  #   granularity=60*60,
  #   start=(datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat(),
  #   stop=datetime.datetime.now().isoformat()
  # )

  # min([candle['low'] for candle in candles])

  # https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
  # the API just returns an ordered array, which is insane
  """
    [
    1499040000000,      // Open time
    "0.01634790",       // Open
    "0.80000000",       // High
    "0.01575800",       // Low
    "0.01577100",       // Close
    "148976.11427815",  // Volume
    1499644799999,      // Close time
    "2434.19055334",    // Quote asset volume
    308,                // Number of trades
    "1756.87402397",    // Taker buy base asset volume
    "28.46694368",      // Taker buy quote asset volume
    "17928899.62484339" // Ignore.
  ]
  """

  candles = public_binance_client.get_klines(
    symbol=purchasing_symbol,
    interval='1h'
  )

  return Decimal(min([candle[3] for candle in candles]))

def can_buy_in_coinbase(symbol, purchasing_currency):
  for coin in coinbase_exchange:
    if coin['base_currency'] == symbol and coin['quote_currency'] == purchasing_currency:
      return True

# TODO should do error handling for non-USD currencies
# TODO should exchange type be specified?
def price_of_symbol(symbol, purchasing_currency):
  pricing_symbol = symbol + purchasing_currency

  if pricing_symbol in binance_prices:
    return binance_prices[pricing_symbol]
  else:
    log.info("price not available in binance, pulling from coinmarket cap", symbol=pricing_symbol)

    # TODO need to get cached coinmarket cap data and pull via:
    # ['quote']['USD']['price']

    # TODO should pull from coinmarket cap or something
    return 0

def binance_purchase_minimum() -> float:
  return 10.0

def binance_normalize_purchase_amount(amount: t.Union[str, Decimal], symbol: str) -> str:
  symbol_info = public_binance_client.get_symbol_info(symbol)

  # not 100% sure of the logic below, but I imagine it's possible for the quote asset precision
  # and the step size precision to be different. In this case, to satisfy both filters, we'd need to pick the min
  # asset_rounding_precision = symbol_info['quoteAssetPrecision']

  # the quote precision is not what we need to round by, the stepSize needs to be used instead:
  # https://github.com/sammchardy/python-binance/issues/219
  step_size = next(f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
  step_size_rounding_precision = int(round(-math.log(float(step_size), 10), 0))

  # rounding_precision = min(asset_rounding_precision, step_size_rounding_precision)
  rounding_precision = step_size_rounding_precision
  return format(Decimal(amount), f"0.{rounding_precision}f")

def binance_normalize_price(amount: t.Union[str, Decimal], symbol: str) -> str:
  symbol_info = public_binance_client.get_symbol_info(symbol)

  asset_rounding_precision = symbol_info['quoteAssetPrecision']

  tick_size = next(f['tickSize'] for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
  tick_size_rounding_precision = int(round(-math.log(float(tick_size), 10), 0))

  rounding_precision = min(asset_rounding_precision, tick_size_rounding_precision)

  return format(Decimal(amount), f"0.{rounding_precision}f")

def binance_open_orders(user: User) -> t.List[CryptoBalance]:
  return [
    {
      # TODO PURCHASING_CURRENCY should make this dynamic for different purchasing currencies
      # cut off the 'USD' at the end of the symbol
      'symbol': order['symbol'][:-3],
      'amount': Decimal(order['origQty']),
      'usd_price': Decimal(order['price']),
      'usd_total': Decimal(order['origQty']) * Decimal(order['price']),
    }

    for order in user.binance_client().get_open_orders()
    if order['side'] == 'BUY'
  ]

def binance_portfolio(user: User) -> t.List[CryptoBalance]:
  account = user.binance_client().get_account()
  purchasing_currency = user.purchasing_currency

  return [
    # TODO basically returns an incomplete CryptoBalance that will be augmented with additional fields later on
    # TODO unsure of how to represent this well in python's typing system
    CryptoBalance(**{
      'symbol': balance['asset'],
      'amount': float(balance['free']),
    })
    for balance in account['balances']
    if float(balance['free']) > 0
  ]