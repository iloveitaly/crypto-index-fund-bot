import typing as t
from decimal import Decimal

from . import (
    convert_stablecoins,
    exchanges,
    market_buy,
    market_cap,
    open_orders,
    portfolio,
)
from .data_types import (
    CryptoBalance,
    ExchangeOrder,
    MarketBuy,
    MarketBuyStrategy,
    SupportedExchanges,
)
from .user import User


# TODO not really sure the best pattern for implementing the command/interactor pattern but we are going to give this a try
class PortfolioCommand:
    @classmethod
    def execute(cls, user: User) -> t.List[CryptoBalance]:
        portfolio_target = market_cap.coins_with_market_cap(user)
        external_portfolio = user.external_portfolio
        user_portfolio = []

        # pull a raw binance reportfolio from exchanges.py and add percentage allocations to it
        for exchange in user.exchanges:
            user_portfolio = exchanges.portfolio(exchange, user)
            # TODO when we actually support multiple exchanges we'll need to do something like this
            # user_portfolio = portfolio.merge_portfolio(user_portfolio, external_portfolio)

        user_portfolio = portfolio.merge_portfolio(user_portfolio, external_portfolio)
        user_portfolio = portfolio.add_price_to_portfolio(user_portfolio, user.purchasing_currency)
        user_portfolio = portfolio.portfolio_with_allocation_percentages(user_portfolio)
        user_portfolio = portfolio.add_missing_assets_to_portfolio(user, user_portfolio, portfolio_target)
        user_portfolio = portfolio.add_percentage_target_to_portfolio(user_portfolio, portfolio_target)

        # TODO https://github.com/python/typing/issues/760
        # highest percentages first in the output table
        user_portfolio.sort(key=lambda balance: balance["target_percentage"], reverse=True)

        return user_portfolio


class BuyCommand:
    # TODO we should break this up into smaller functions
    @classmethod
    def execute(
        cls, user: User, purchase_balance: t.Optional[Decimal] = None
    ) -> t.List[t.Tuple[SupportedExchanges, Decimal, t.List[MarketBuy], t.List[ExchangeOrder]]]:
        if user.buy_strategy == MarketBuyStrategy.LIMIT and user.cancel_stale_orders:
            for exchange in user.exchanges:
                open_orders.cancel_stale_open_orders(user, exchange)

        # calculates the porfolio target across all supported exchanges
        portfolio_target = market_cap.coins_with_market_cap(user)
        merged_portfolio = user.external_portfolio
        purchase_balance_for_exchange: t.Dict[SupportedExchanges, Decimal] = {}

        for exchange in user.exchanges:
            exchange_portfolio = exchanges.portfolio(exchange, user)

            if user.convert_stablecoins:
                convert_stablecoins.convert_stablecoins(user, exchange, exchange_portfolio)
                # TODO we should wait for the stablecoin sells to clear and then refresh the portfolio

            # TODO we need to determine how coinbase handles purchasing currencies

            purchase_balance_for_exchange[exchange] = market_buy.purchasing_currency_in_portfolio(user, exchange_portfolio)
            merged_portfolio = portfolio.merge_portfolio(merged_portfolio, exchange_portfolio)

        merged_portfolio = portfolio.add_price_to_portfolio(merged_portfolio, user.purchasing_currency)
        merged_portfolio = portfolio.portfolio_with_allocation_percentages(merged_portfolio)

        # TODO we should protect against specifying purchasing currency when in livemode
        #      also, I don't love that this parameter is passed in, feels odd
        if purchase_balance:
            for e in purchase_balance_for_exchange:
                purchase_balance_for_exchange[e] = purchase_balance

        results_by_exchange = []

        # now that we have allocations across all portfolios, let's buy in each portfolio
        for exchange in user.exchanges:
            sorted_market_buys = market_buy.calculate_market_buy_preferences(
                target_index=portfolio_target,
                merged_portfolio=merged_portfolio,
                deprioritized_coins=user.deprioritized_coins,
                user=user,
                exchange=exchange,
            )

            exchange_purchase_balance = purchase_balance_for_exchange[exchange]

            market_buys = market_buy.determine_market_buys(
                user=user,
                sorted_buy_preferences=sorted_market_buys,
                merged_portfolio=merged_portfolio,
                target_portfolio=portfolio_target,
                purchase_balance=exchange_purchase_balance,
                exchange=exchange,
            )

            completed_orders = market_buy.make_market_buys(user, market_buys)

            results_by_exchange.append((exchange, exchange_purchase_balance, market_buys, completed_orders))

        return results_by_exchange
