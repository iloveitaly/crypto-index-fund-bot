import typing as t
from data_types import MarketBuy, MarketIndexStrategy, MarketBuyStrategy, CryptoBalance
from utils import log

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
  user.cancel_stale_orders = os.getenv("USER_CANCEL_STALE_ORDERS", 'false').lower() == 'true'

  if index_strategy := os.getenv("USER_INDEX_STRATEGY"):
    user.index_strategy = index_strategy

  if buy_strategy := os.getenv("USER_BUY_STRATEGY"):
    user.buy_strategy = buy_strategy

  try:
    user.external_portfolio = json.load(open('external_portfolio.json'))
    log.debug("loaded external portfolio")
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
  purchasing_currency: str = 'USD'
  purchase_max: int = 50
  purchase_min: int = 30
  excluded_tags: t.List[str] = ['wrapped-tokens', 'stablecoin']
  exchanges: t.List[str] = ['binance']

  def __init__(self):
    pass

  def binance_client(self):
    from binance.client import Client

    # TODO memoize client
    # TODO error check for empty keys?

    return Client(
      self.binance_api_key,
      self.binance_secret_key,

      tld='us'
    )
