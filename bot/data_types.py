import typing
import enum

CryptoBalance = typing.TypedDict('CryptoBalance', {
  'symbol': str,
  # could be quantity?
  'amount': float,
  'usd_price': float,
  'usd_total': float,
  'percentage': float,
  'target_percentage': float
})

CryptoData = typing.TypedDict('CryptoData', {
  # symbol is not a pair
  'symbol': str,
  'market_cap': int,
  # should really be 'market_cap_percentage'
  'percentage': float,
  '7d_change': float,
  '30d_change': float
})

MarketBuy = typing.TypedDict('MarketBuy', {
  "symbol": str,
  "amount": float,
})

class MarketBuyStrategy(str, enum.Enum):
  LIMIT = 'limit'
  MARKET = 'market'

# by subclassing str you can use == to compare strings to enums
class MarketIndexStrategy(str, enum.Enum):
  MARKET_CAP = 'market_cap'
  SQRT_MARKET_CAP = 'sqrt_market_cap'
  SMA = 'sma'