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
  def __init__(self):
    self.livemode = False
    self.binance_api_key = ''
    self.binance_secret_key = ''
    self.external_portfolio = []
    self.convert_stablecoins = False

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
