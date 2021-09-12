import typing as t
from decimal import Decimal

from ..data_types import CryptoBalance, CryptoData
from ..user import User


def binance_portfolio(user: User) -> t.List[CryptoBalance]:
    account = user.binance_client().get_account()

    # TODO return an incomplete CryptoBalance that will be augmented with additional fields later on
    return [
        CryptoBalance(
            symbol=balance["asset"],
            amount=Decimal(balance["free"]),
            # to satisify typer; hopefully there is a better way to do this in the future
            usd_price=Decimal(0),
            usd_total=Decimal(0),
            percentage=Decimal(0),
            target_percentage=Decimal(0),
        )
        for balance in account["balances"]
        if float(balance["free"]) > 0
    ]
