from data_types import CryptoData, CryptoBalance
from typing import List

from user import user_from_env, User
from utils import log

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

def can_buy_amount_in_exchange(symbol: str, amount_in_purchasing_currency: float):
  binance_symbol_info = public_binance_client.get_symbol_info(symbol)

  # the min notional amount specified on the symbol data is the min in USD
  # that needs to be purchased. This min is enforced upstream, so we can avoid
  # that check here

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
    # TODO should pull from coinmarket cap or something
    return 1

def binance_portfolio(user: User) -> List[CryptoBalance]:
  account = user.binance_client().get_account()
  purchasing_currency = user.purchasing_currency()

  return [
    # TODO basically returns an incomplete CryptoBalance that will be augmented with additional fields later on
    # TODO unsure of how to represent this well in python's typing system
    {
      'symbol': balance['asset'],
      'amount': float(balance['free']),
    }
    for balance in account['balances']
    if float(balance['free']) > 0
  ]

# run script directly to get a report on coinbase vs binance coin stats
if __name__ == "__main__":
  coinbase_available_coins = set([coin['base_currency'] for coin in coinbase_exchange])
  binance_available_coins = set([coin['baseAsset'] for coin in binance_exchange['symbols']])

  print("Available, regardless of purchasing currency:")
  print(f"coinbase:\t{len(coinbase_available_coins)}")
  print(f"binance:\t{len(binance_available_coins)}")

  user = user_from_env()

  coinbase_available_coins_in_purchasing_currency = set([coin['base_currency'] for coin in coinbase_exchange if coin['quote_currency'] == user.purchasing_currency()])
  binance_available_coins_in_purchasing_currency = set([coin['baseAsset'] for coin in binance_exchange['symbols'] if coin['quoteAsset'] == user.purchasing_currency()])

  print("\nAvailable in purchasing currency:")
  print(f"coinbase:\t{len(coinbase_available_coins_in_purchasing_currency)}")
  print(f"binance:\t{len(binance_available_coins_in_purchasing_currency)}")
