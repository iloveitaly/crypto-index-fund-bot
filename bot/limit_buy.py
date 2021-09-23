from decimal import Decimal

from . import exchanges
from .user import User
from .utils import log

# TODO this logic isn't scientific in any way, mostly a playground


def determine_limit_price(user: User, symbol: str, purchasing_currency: str) -> Decimal:
    # TODO this is binance-specific right now, refactor this out

    trading_pair = symbol + purchasing_currency

    client = user.binance_client()

    # order depth returns the lowest asks and the highest bids
    # increasing limits returns lower bids and higher asks
    # grab a long-ish order book to get some analytics on the order book

    order_book = client.get_order_book(symbol=trading_pair, limit=100)

    # price that binance reports is at the bottom of the order book
    # looks like they use the bottom of the ask stack to clear market orders (makes sense)
    # cannot determine if the orders in the book are market, limit, or other order types.
    # I wonder if other exchanges expose that sort of information?
    lowest_ask = order_book["asks"][0][0]
    highest_bid = order_book["bids"][0][0]

    ask_difference = Decimal(highest_bid) - Decimal(lowest_ask)

    # TODO can we inspect the low price and determine the volume that was traded at that price point?
    last_day_low = low_over_last_day(user, trading_pair)

    log.warn(
        "price analytics",
        symbol=trading_pair,
        ask_bid_difference=ask_difference,
        ask_bid_percentage_difference=ask_difference / Decimal(lowest_ask) * -100,
        last_day_low_difference=100 - (last_day_low / Decimal(lowest_ask) * 100),
        bid=highest_bid,
        ask=lowest_ask,
        last_day_low=last_day_low,
        reported_price=exchanges.binance_price_for_symbol(trading_pair),
    )

    # TODO calculate momentum, or low price over last 24hrs, to determine the ideal drop price
    # TODO pull percentage drop attempt from user model

    limit_price = min(Decimal(highest_bid), Decimal(lowest_ask) * Decimal(0.97))
    limit_price = min(last_day_low, limit_price)

    # TODO can we inspect the order book depth here? Or general liquidity for the market?
    #      what else can we do to improve our purchase strategy?

    # TODO add option to use the midpoint, or some other position, of the order book instead of the lowest ask

    return limit_price


def low_over_last_day(user: User, trading_pair: str) -> Decimal:
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

    candles = user.binance_client().get_klines(symbol=trading_pair, interval="1h")

    return Decimal(min([candle[3] for candle in candles]))
