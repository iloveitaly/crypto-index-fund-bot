import typing as t

from .user import User
from .data_types import CryptoBalance, MarketBuyStrategy

from . import exchanges
from . import convert_stablecoins
from . import open_orders
from . import portfolio
from . import market_cap
from . import market_buy


# TODO not really sure the best pattern for implementing the command/interactor pattern but we are going to give this a try
class PortfolioCommand:
  @classmethod
  def execute(cls, user: User) -> t.List[CryptoBalance]:
    # from market_cap import coins_with_market_cap
    # from exchanges import binance_portfolio
    # import bot.market_cap
    # import portfolio

    portfolio_target = market_cap.coins_with_market_cap(user)

    external_portfolio = user.external_portfolio

    # pull a raw binance reportfolio from exchanges.py and add percentage allocations to it
    user_portfolio = exchanges.binance_portfolio(user)
    user_portfolio = portfolio.merge_portfolio(user_portfolio, external_portfolio)
    user_portfolio = portfolio.add_price_to_portfolio(user_portfolio, user.purchasing_currency)
    user_portfolio = portfolio.portfolio_with_allocation_percentages(user_portfolio)
    user_portfolio = portfolio.add_missing_assets_to_portfolio(user, user_portfolio, portfolio_target)
    user_portfolio = portfolio.add_percentage_target_to_portfolio(user_portfolio, portfolio_target)

    # TODO https://github.com/python/typing/issues/760
    # highest percentages first in the output table
    user_portfolio.sort(key=lambda balance: balance['target_percentage'], reverse=True)

    return user_portfolio

class BuyCommand:
  # TODO we should break this up into smaller functions
  @classmethod
  def execute(cls, user: User, purchase_balance: t.Optional[float] = None) -> t.Tuple[float, t.List, t.List]:
    if user.buy_strategy == MarketBuyStrategy.LIMIT and user.cancel_stale_orders:
      open_orders.cancel_stale_open_orders(user)

    current_portfolio = exchanges.binance_portfolio(user)

    if user.convert_stablecoins:
      convert_stablecoins.convert_stablecoins(user, current_portfolio)

    external_portfolio = user.external_portfolio
    external_portfolio = portfolio.add_price_to_portfolio(external_portfolio, user.purchasing_currency)

    current_portfolio = portfolio.merge_portfolio(current_portfolio, external_portfolio)
    current_portfolio = portfolio.add_price_to_portfolio(current_portfolio, user.purchasing_currency)
    current_portfolio = portfolio.portfolio_with_allocation_percentages(current_portfolio)

    # TODO we should protect against specifying purchasing currency when in livemode
    #      also, I don't love that this parameter is passed in, feels odd
    if not purchase_balance:
      purchase_balance = market_buy.purchasing_currency_in_portfolio(user, current_portfolio)

    portfolio_target = market_cap.coins_with_market_cap(user)
    sorted_market_buys = market_buy.calculate_market_buy_preferences(portfolio_target, current_portfolio)
    market_buys = market_buy.determine_market_buys(user, sorted_market_buys, current_portfolio, portfolio_target, purchase_balance)

    completed_orders = market_buy.make_market_buys(user, market_buys)

    return (purchase_balance, market_buys, completed_orders)
