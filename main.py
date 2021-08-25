import click
import utils

from utils import log
from user import user_from_env
from data_types import MarketIndexStrategy

# if you use `cod` it's helpful to disable while you are hacking on the CLI
# if you are on zsh:
#   `preexec_functions=(${preexec_functions#__cod_preexec_zsh})`

@click.group(help="Tool for building your own crypto index fund.")
# TODO this must be specified before the subcommand, which is a strange requirement. I wonder if there is a way around this.
@click.option("--verbose", "-v", is_flag=True, help="Enables verbose mode.")
def cli(verbose):
  if verbose:
    utils.setLevel('INFO')

@cli.command(help="Analyize configured exchanges")
def analyze():
  import exchanges

  coinbase_available_coins = set([coin['base_currency'] for coin in exchanges.coinbase_exchange])
  binance_available_coins = set([coin['baseAsset'] for coin in exchanges.binance_exchange['symbols']])

  print("Available, regardless of purchasing currency:")
  print(f"coinbase:\t{len(coinbase_available_coins)}")
  print(f"binance:\t{len(binance_available_coins)}")

  user = user_from_env()

  coinbase_available_coins_in_purchasing_currency = set([coin['base_currency'] for coin in exchanges.coinbase_exchange if coin['quote_currency'] == user.purchasing_currency])
  binance_available_coins_in_purchasing_currency = set([coin['baseAsset'] for coin in exchanges.binance_exchange['symbols'] if coin['quoteAsset'] == user.purchasing_currency])

  print("\nAvailable in purchasing currency:")
  print(f"coinbase:\t{len(coinbase_available_coins_in_purchasing_currency)}")
  print(f"binance:\t{len(binance_available_coins_in_purchasing_currency)}")

@cli.command(help="Print index by market cap")
@click.option("-f", "--format", type=click.Choice(['md', 'csv']), default="md", show_default=True, help="Output format")
@click.option("-s", "--strategy", type=click.Choice([choice.value for choice in MarketIndexStrategy]), default=MarketIndexStrategy.MARKET_CAP, show_default=True, help="Index strategy")
@click.option("-l", "--limit", type=int, help="Maximum size of index")
def index(format, limit, strategy):
  import market_cap

  user = user_from_env()

  if strategy:
    user.index_strategy = strategy

  if limit:
    user.index_limit = limit

  coins_by_exchange = market_cap.coins_with_market_cap(user)

  log.info("writing market cap csv")

  if format == 'md':
    click.echo(utils.table_output(coins_by_exchange))
  else:
    click.echo(utils.csv_output(coins_by_exchange))

@cli.command(help="Print current portfolio with targets")
@click.option("-f", "--format", type=click.Choice(['md', 'csv']), default="md", show_default=True, help="Output format")
def portfolio(format):
  from market_cap import coins_with_market_cap
  from exchanges import binance_portfolio
  import portfolio

  user = user_from_env()
  portfolio_target = coins_with_market_cap(user)

  external_portfolio = user.external_portfolio

  # pull a raw binance reportfolio from exchanges.py and add percentage allocations to it
  user_portfolio = binance_portfolio(user)
  user_portfolio = portfolio.merge_portfolio(user_portfolio, external_portfolio)
  user_portfolio = portfolio.add_price_to_portfolio(user_portfolio, user.purchasing_currency)
  user_portfolio = portfolio.portfolio_with_allocation_percentages(user_portfolio)
  user_portfolio = portfolio.add_missing_assets_to_portfolio(user, user_portfolio, portfolio_target)
  user_portfolio = portfolio.add_percentage_target_to_portfolio(user_portfolio, portfolio_target)

  # highest percentages first in the output table
  user_portfolio.sort(key=lambda balance: balance['target_percentage'], reverse=True)

  from utils import table_output, csv_output
  if format == 'md':
    click.echo(table_output(user_portfolio))
  else:
    click.echo(csv_output(user_portfolio))

  import market_buy
  purchase_balance = market_buy.purchasing_currency_in_portfolio(user, user_portfolio)
  click.echo(f"\nPurchasing Balance: {purchase_balance}")

@cli.command(
  short_help="Buy additional tokens for your index",
  help="Buys additional tokens using purchasing currency in your exchange(s)"
)
@click.option("-f", "--format", type=click.Choice(['md', 'csv']), default="md", show_default=True, help="Output format")
@click.option("-d", "--dry-run", is_flag=True, help="Dry run, do not buy coins")
@click.option("-p", "--purchase-balance", type=float, help="Dry-run with a specific amount of purchasing currency")
@click.option("-c", "--convert", is_flag=True, help="Convert all stablecoin equivilents to purchasing currency. Overrides user configuration.")
@click.option("--cancel-orders", is_flag=True, help="Cancel all stale orders")
def buy(format, dry_run, purchase_balance, convert, cancel_orders):
  from commands import BuyCommand

  if purchase_balance:
    log.info("dry run using fake purchase balance", purchase_balance=purchase_balance)
    dry_run = True

  user = user_from_env()

  # if user is in testmode, assume user wants dry run
  if not dry_run and not user.livemode:
    dry_run = True

  if dry_run:
    click.secho(f"Bot running in dry-run mode\n", fg='green')

  if convert:
    user.convert_stablecoins = True

  if cancel_orders:
    user.cancel_stale_orders = True

  if dry_run:
    user.convert_stablecoins = False
    user.cancel_stale_orders = False
    user.livemode = False

  purchase_balance, market_buys, completed_orders = BuyCommand.execute(user, purchase_balance)

  click.secho(f"Purchasing Balance: {purchase_balance}\n", fg='green')

  if format == 'md':
    click.echo(utils.table_output(market_buys))
  else:
    click.echo(utils.csv_output(market_buys))

  if not market_buys:
    click.secho("\nNot enough purchasing currency to make any trades.", fg='red')
  else:
    purchased_token_list = ', '.join([order["symbol"] for order in completed_orders])
    click.secho(f"\nSuccessfully purchased: {purchased_token_list}", fg='green')

if __name__ == '__main__':
    cli()