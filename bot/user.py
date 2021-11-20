import decimal
import functools
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

    user.binance_api_key = t.cast(str, config("USER_BINANCE_API_KEY"))
    user.binance_secret_key = t.cast(str, config("USER_BINANCE_SECRET_KEY"))

    external_porfolio_json = config("USER_EXTERNAL_PORTFOLIO", None)
    if external_porfolio_json:
        user.external_portfolio = json.loads(external_porfolio_json)
    else:
        try:
            user.external_portfolio = json.load(open("external_portfolio.json"), parse_float=decimal.Decimal)
            log.debug("loaded 'external_portfolio.json'")
        except FileNotFoundError:
            pass

    user_preferences = json.loads(t.cast(str, config("USER_PREFERENCES", "{}")))

    for k, v in user_preferences.items():
        setattr(user, k, v)

    return user


class User:
    binance_api_key: t.Optional[str] = ""
    binance_secret_key: t.Optional[str] = ""
    external_portfolio: t.List[CryptoBalance] = []
    livemode: bool = False

    # self explanatory common purchasing configurations
    purchasing_currency: str = "USD"
    purchase_max: int = 25
    purchase_min: int = 10
    exchanges: t.List[SupportedExchanges] = [SupportedExchanges.BINANCE]

    index_strategy: MarketIndexStrategy = MarketIndexStrategy.MARKET_CAP
    index_strategy_sqrt_adjustment: t.Optional[str] = None
    buy_strategy: MarketBuyStrategy = MarketBuyStrategy.MARKET
    # automatically sell stablecoins to USD / purchasing currency?
    convert_stablecoins: bool = True
    # max number of items in the market index
    index_limit: t.Optional[int] = None

    # if you use a limit purchase stratregy, the bot can automatically cancel orders that are stale/old
    cancel_stale_orders: bool = True
    stale_order_hour_limit: int = 24

    # coins you'd like to exclude completely from your index
    excluded_coins: t.List[str] = []
    # coins you'd like to purchase last, after all other coin purchases have been satisfied
    deprioritized_coins: t.List[str] = ["BNB", "DOGE", "XRP", "STORJ"]
    # coinmarketcap tags to exclude completely
    excluded_tags: t.List[str] = ["wrapped-tokens", "stablecoin"]

    # if the current holding % / target holding % multiple is greater than this value, prioritize purchasing it above other tokens
    # this is useful if you want to avoid constantly purchasing tokens with smaller total market cap at the risk of not correcting
    # your allocation on coins with a higher total market cap
    allocation_drift_multiple_limit: t.Optional[int] = 5

    # if the absolute percentage of a holding drifts this amount, prioritize purchasing it even above the % drift multiple above
    allocation_drift_percentage_limit: t.Optional[int] = None

    def __init__(self):
        pass

    def is_primary_exchange(self, exchange: SupportedExchanges) -> bool:
        return exchange == self.exchanges[0]

    @functools.cache
    def binance_client(self):
        from binance.client import Client

        # TODO error check for empty keys?

        return Client(self.binance_api_key, self.binance_secret_key, tld="us")
