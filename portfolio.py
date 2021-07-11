from market_cap import coins_with_market_cap

from user import User
from exchanges import price_of_symbol

from data_types import CryptoBalance, CryptoData
from typing import List

def portfolio_with_allocation_percentages(portfolio) -> List[CryptoBalance]:
  import math
  total = math.fsum([balance['usd_price'] * balance['amount'] for balance in portfolio])

  return [
    balance | {
      'usd_total' : usd_total,
      'percentage' : usd_total / total * 100.0,
    }
    for balance in portfolio

    # this is silly: we are only using a conditional here to assign `usd_total`
    if (usd_total := balance['usd_price'] * balance['amount'])
  ]

# useful for adding in externally held assets
def merge_portfolio(portfolio_1: List[CryptoBalance], portfolio_2: List[CryptoBalance]) -> List[CryptoBalance]:
  new_portfolio = []

  for balance in portfolio_1:
    portfolio_2_balance = next((portfolio_2_balance for portfolio_2_balance in portfolio_2 if portfolio_2_balance['symbol'] == balance['symbol']), None)

    # if an asset is in porfolio 2, combine them
    if portfolio_2_balance:
      new_portfolio.append(balance | {
        'amount': balance['amount'] + portfolio_2_balance['amount'],
      })
    else:
      new_portfolio.append(balance)

  # add in any new assets from the 2nd portfolio
  for balance in portfolio_2:
    if balance['symbol'] not in [balance['symbol'] for balance in new_portfolio]:
      new_portfolio.append(balance)

  return new_portfolio

def add_price_to_portfolio(portfolio: List[CryptoBalance], purchasing_currency: str):
  return [
    balance | {
      'usd_price': price_of_symbol(balance['symbol'], purchasing_currency) if balance['symbol'] != purchasing_currency else 1,
    }
    for balance in portfolio
  ]

# TODO maybe remove user preference? The target porfolio should take into the account the user's purchasing currency preference?
def add_missing_assets_to_portfolio(user: User, portfolio, portfolio_target: List[CryptoBalance]) -> List[CryptoBalance]:
  from exchanges import binance_prices
  purchasing_currency = user.purchasing_currency()

  return portfolio + [
    {
      "symbol": balance['symbol'],
      "usd_price": binance_prices[balance['symbol'] + purchasing_currency],
      "amount": 0,
      "usd_total": 0,
      "percentage": 0
    }
    for balance in portfolio_target
    if balance['symbol'] not in [balance['symbol'] for balance in portfolio]
  ]

# right now, this is for tinkering/debugging purposes only
def add_percentage_target_to_portfolio(portfolio, portfolio_target: List[CryptoBalance]):
  return [
    balance | {
      'target_percentage':

      # `next` is a little trick to return the first match in a list comprehension
      # https://stackoverflow.com/questions/9542738/python-find-in-list
      next(
        (
          target['percentage']
          for target in portfolio_target
          if target['symbol'] == balance['symbol']
        ),

        # coin may exist in portfolio but not available for purchase
        # this can occur if deposits are allowed but trades are not
        0.0
      ),
    }
    for balance in portfolio
  ]

# run directly to output target portfolio index
if __name__ == "__main__":
  from user import user_from_env
  from exchanges import binance_portfolio

  user = user_from_env()
  portfolio_target = coins_with_market_cap(user)

  external_portfolio = user.external_portfolio

  # pull a raw binance reportfolio from exchanges.py and add percentage allocations to it
  portfolio = binance_portfolio(user)
  portfolio = merge_portfolio(portfolio, external_portfolio)
  portfolio = add_price_to_portfolio(portfolio, user.purchasing_currency())
  portfolio = portfolio_with_allocation_percentages(portfolio)
  portfolio = add_missing_assets_to_portfolio(user, portfolio, portfolio_target)
  portfolio = add_percentage_target_to_portfolio(portfolio, portfolio_target)

  # highest percentages first in the output table
  portfolio.sort(key=lambda balance: balance['target_percentage'], reverse=True)

  from utils import table_output
  table_output(portfolio)
