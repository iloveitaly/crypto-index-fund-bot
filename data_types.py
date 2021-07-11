import typing

CryptoBalance = typing.TypedDict('CryptoBalance', {
  'symbol': str,
  # could be quantity?
  'amount': float,
  'usd_price': float,
  'usd_total': float,
  'percentage': float,
})

CryptoData = typing.TypedDict('CryptoData', {
  'symbol': str,
  'market_cap': int,
  'percentage': float,
  '7d_change': float,
  '30d_change': float
})

MarketBuy = typing.TypedDict('MarketBuy', {
  "symbol": str,
  "amount": float,
})