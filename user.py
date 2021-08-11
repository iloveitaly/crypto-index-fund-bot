import typing as t
from data_types import MarketBuy, MarketIndexStrategy, MarketBuyStrategy, CryptoBalance

from dotenv import load_dotenv
load_dotenv()

# right now, this is the only way to use User
# in the future, User could easily be wired up to an ORM
def user_from_env():
  import os
  import json

  user = User()
  user.binance_api_key = os.getenv("USER_BINANCE_API_KEY")
  user.binance_secret_key = os.getenv("USER_BINANCE_SECRET_KEY")
  user.livemode = os.getenv("USER_LIVEMODE", 'false').lower() == 'true'
  user.convert_stablecoins = os.getenv("USER_CONVERT_STABLECOINS", 'false').lower() == 'true'

  try:
    user.external_portfolio = json.load(open('external_portfolio.json'))
  except FileNotFoundError:
    pass

  return user

class User:
  index_strategy: MarketIndexStrategy = MarketIndexStrategy.MARKET_CAP
  buy_strategy: MarketBuyStrategy = MarketBuyStrategy.LIMIT
  binance_api_key: str = ''
  binance_secret_key: str = ''
  external_portfolio: t.List[CryptoBalance] = []
  convert_stablecoins: bool = False
  index_limit: t.Optional[int] = None
  livemode: bool = False
  cancel_stale_orders: bool = True
  stale_order_hour_limit: int = 24
  excluded_coins: t.List[str] = []

  def __init__(self):
    pass

  def exchanges(self):
    return ['binance']

  def binance_client(self):
    from binance.client import Client

    # TODO memoize this
    return Client(
      self.binance_api_key,
      self.binance_secret_key,

      tld='us'
    )

  def purchasing_currency(self):
    return 'USD'

  def purchase_max(self):
    return 50

  def purchase_min(self):
    return 30

  def excluded_tags(self):
    return ['wrapped-tokens', 'stablecoin']
