from .user import User
from . import exchanges
from decimal import Decimal

from .data_types import CryptoBalance, CryptoData
import typing as t


def portfolio_with_allocation_percentages(portfolio: t.List[CryptoBalance]) -> t.List[CryptoBalance]:
    portfolio_total = sum([balance["usd_price"] * balance["amount"] for balance in portfolio])

    return [
        balance
        | {
            "usd_total": usd_total,
            "percentage": usd_total / portfolio_total * Decimal(100),
        }
        for balance in portfolio
        # this is silly: we are only using a conditional here to assign `usd_total`
        if (usd_total := balance["usd_price"] * balance["amount"])
    ]


# useful for adding in externally held assets
# in the future, we'll also use this for merging portfolios from multiple exchanges
def merge_portfolio(portfolio_1: t.List[CryptoBalance], portfolio_2: t.List[CryptoBalance]) -> t.List[CryptoBalance]:
    new_portfolio = []

    for balance in portfolio_1:
        portfolio_2_balance = next(
            (portfolio_2_balance for portfolio_2_balance in portfolio_2 if portfolio_2_balance["symbol"] == balance["symbol"]), None
        )

        # if an asset is in porfolio 2, combine them
        if portfolio_2_balance:
            new_portfolio.append(
                balance
                | {
                    "amount": balance["amount"] + portfolio_2_balance["amount"],
                }
            )
        else:
            new_portfolio.append(balance)

    # add in any new assets from the 2nd portfolio
    for balance in portfolio_2:
        if balance["symbol"] not in [balance["symbol"] for balance in new_portfolio]:
            new_portfolio.append(balance)

    return new_portfolio


def add_price_to_portfolio(portfolio: t.List[CryptoBalance], purchasing_currency: str) -> t.List[CryptoBalance]:
    return [
        # TODO the new python dict merge syntax doesn't seem to play well with typed dicts
        balance
        | {
            "usd_price": exchanges.price_of_symbol(balance["symbol"], purchasing_currency) if balance["symbol"] != purchasing_currency else 1,
        }
        for balance in portfolio
    ]


# TODO maybe remove user preference? The target porfolio should take into the account the user's purchasing currency preference?
def add_missing_assets_to_portfolio(user: User, portfolio: t.List[CryptoBalance], portfolio_target: t.List[CryptoData]) -> t.List[CryptoBalance]:
    from . import exchanges

    purchasing_currency = user.purchasing_currency

    return portfolio + [
        CryptoBalance(
            symbol=balance["symbol"],
            usd_price=exchanges.binance_price_for_symbol(balance["symbol"] + purchasing_currency),
            amount=Decimal(0),
            # we can't mark specific arguments as optional, so instead we pass a value that will be ignored
            target_percentage=Decimal(0),
            usd_total=Decimal(0),
            percentage=Decimal(0),
        )
        for balance in portfolio_target
        if balance["symbol"] not in [balance["symbol"] for balance in portfolio]
    ]


# right now, this is for tinkering/debugging purposes only
def add_percentage_target_to_portfolio(portfolio: t.List[CryptoBalance], portfolio_target: t.List[CryptoData]) -> t.List[CryptoBalance]:
    return [
        # updating TypedDicts is not simple https://github.com/python/mypy/issues/6462
        balance
        | {
            "target_percentage":
            # `next` is a little trick to return the first match in a list comprehension
            # https://stackoverflow.com/questions/9542738/python-find-in-list
            next(
                (target["percentage"] for target in portfolio_target if target["symbol"] == balance["symbol"]),
                # coin may exist in portfolio but not available for purchase
                # this can occur if deposits are allowed but trades are not
                Decimal(0),
            ),
        }
        for balance in portfolio
    ]
