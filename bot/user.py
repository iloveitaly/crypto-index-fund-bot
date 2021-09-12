import decimal
import typing as t

from .data_types import (
    CryptoBalance,
    MarketBuyStrategy,
    MarketIndexStrategy,
    SupportedExchanges,
)
from .utils import log


# right now, this is the only way to use User
# in the future, User could easily be wired up to an ORM
def user_from_env():
    import json

    from decouple import config

    user = User()
    user.binance_api_key = t.cast(str, config("USER_BINANCE_API_KEY", ""))
    user.binance_secret_key = t.cast(str, config("USER_BINANCE_SECRET_KEY", ""))

    user.livemode = t.cast(str, config("USER_LIVEMODE", "false")).lower() == "true"
    user.convert_stablecoins = t.cast(str, config("USER_CONVERT_STABLECOINS", "false")).lower() == "true"
    user.cancel_stale_orders = t.cast(str, config("USER_CANCEL_STALE_ORDERS", "false")).lower() == "true"

    if index_strategy := config("USER_INDEX_STRATEGY", default=None):
        user.index_strategy = MarketIndexStrategy(index_strategy)

    if buy_strategy := config("USER_BUY_STRATEGY", default=None):
        user.buy_strategy = MarketBuyStrategy(buy_strategy)

    try:
        user.external_portfolio = json.load(open("external_portfolio.json"), parse_float=decimal.Decimal)
        log.debug("loaded external portfolio")
    except FileNotFoundError:
        pass

    return user


class User:
    index_strategy: MarketIndexStrategy = MarketIndexStrategy.MARKET_CAP
    buy_strategy: MarketBuyStrategy = MarketBuyStrategy.MARKET
    binance_api_key: t.Optional[str] = ""
    binance_secret_key: t.Optional[str] = ""
    external_portfolio: t.List[CryptoBalance] = []
    convert_stablecoins: bool = True
    index_limit: t.Optional[int] = None
    livemode: bool = False
    cancel_stale_orders: bool = True
    stale_order_hour_limit: int = 24
    excluded_coins: t.List[str] = []
    deprioritized_coins: t.List[str] = ["BNB", "DOGE", "XRP"]
    purchasing_currency: str = "USD"
    purchase_max: int = 50
    purchase_min: int = 25
    excluded_tags: t.List[str] = ["wrapped-tokens", "stablecoin"]
    exchanges: t.List[SupportedExchanges] = [SupportedExchanges.BINANCE]

    def __init__(self):
        pass

    def binance_client(self):
        from binance.client import Client

        # TODO memoize client
        # TODO error check for empty keys?

        return Client(self.binance_api_key, self.binance_secret_key, tld="us")
