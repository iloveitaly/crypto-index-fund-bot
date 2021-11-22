from decimal import Decimal

import click
from decouple import config

import bot.market_buy
import bot.market_cap
import bot.user
import bot.utils
from bot.commands import BuyCommand, PortfolioCommand, SellStablecoinsCommand
from bot.data_types import MarketIndexStrategy, SupportedExchanges

# if you use `cod` it's helpful to disable while you are hacking on the CLI
# if you are on zsh:
#   `preexec_functions=(${preexec_functions#__cod_preexec_zsh})`


def user_for_cli():
    user_id = config("USER_ID", default=-1, cast=int)
    if user_id == -1:
        return bot.user.user_from_env()

    import django

    django.setup()

    from users.models import User as DatabaseUser

    return DatabaseUser.objects.get(id=user_id).bot_user()


@click.group(help="Tool for building your own crypto index fund.")
# TODO this must be specified before the subcommand, which is a strange requirement. I wonder if there is a way around this.
@click.option("--verbose", "-v", is_flag=True, help="Enables verbose mode.")
def cli(verbose):
    if verbose:
        bot.utils.setLevel("INFO")


@cli.command(help="Analyze configured exchanges")
def analyze():
    import bot.exchanges as exchanges

    coinbase_available_coins = {coin["base_currency"] for coin in exchanges.coinbase_exchange}
    binance_available_coins = {coin["baseAsset"] for coin in exchanges.binance_all_symbol_info()}

    print("Available, regardless of purchasing currency:")
    print(f"coinbase:\t{len(coinbase_available_coins)}")
    print(f"binance:\t{len(binance_available_coins)}")

    user = user_for_cli()

    coinbase_available_coins_in_purchasing_currency = {
        coin["base_currency"] for coin in exchanges.coinbase_exchange if coin["quote_currency"] == user.purchasing_currency
    }
    binance_available_coins_in_purchasing_currency = {
        coin["baseAsset"] for coin in exchanges.binance_all_symbol_info() if coin["quoteAsset"] == user.purchasing_currency
    }

    print("\nAvailable in purchasing currency:")
    print(f"coinbase:\t{len(coinbase_available_coins_in_purchasing_currency)}")
    print(f"binance:\t{len(binance_available_coins_in_purchasing_currency)}")
    print(
        "binance not available in purchasing currency:\n\n%s\n\n"
        % ("\n".join(binance_available_coins - binance_available_coins_in_purchasing_currency))
    )
    print(
        "unique to coinbase:\n\n%s\n\n"
        % ("\n".join(coinbase_available_coins_in_purchasing_currency - binance_available_coins_in_purchasing_currency))
    )


@cli.command(help="Print index by market cap")
@click.option(
    "-f",
    "--format",
    type=click.Choice(["md", "csv"]),
    default="md",
    show_default=True,
    help="Output format",
)
@click.option(
    "-s",
    "--strategy",
    type=click.Choice([choice.value for choice in MarketIndexStrategy]),
    default=None,
    help="Index strategy",
)
@click.option("-l", "--limit", type=int, help="Maximum size of index")
@click.option("--sqrt-adjustment", type=str, help="Customized sqrt calculation")
def index(format, limit, strategy, sqrt_adjustment):
    user = user_for_cli()

    if strategy:
        user.index_strategy = strategy

    if limit:
        user.index_limit = limit

    if sqrt_adjustment:
        user.index_strategy_sqrt_adjustment = sqrt_adjustment

    coins_by_exchange = bot.market_cap.coins_with_market_cap(user)

    click.echo(bot.utils.table_output_with_format(coins_by_exchange, format))


@cli.command(help="Print current portfolio with targets")
@click.option(
    "-f",
    "--format",
    type=click.Choice(["md", "csv"]),
    default="md",
    show_default=True,
    help="Output format",
)
def portfolio(format):
    user = user_for_cli()
    portfolio = PortfolioCommand.execute(user)

    click.echo(bot.utils.table_output_with_format(portfolio, format))

    purchase_balance = bot.market_buy.purchasing_currency_in_portfolio(user, portfolio)
    click.echo(f"\nPurchasing Balance: {bot.utils.currency_format(purchase_balance)}")

    purchase_total = sum([coin["usd_total"] for coin in portfolio])
    click.echo(f"Portfolio Total: {bot.utils.currency_format(purchase_total)}")


# TODO still very much a WIP
@cli.command(short_help="Calculate cost basis")
def cost_basis():
    user = user_for_cli()
    import ccxt

    exchange = ccxt.binanceus(
        {
            "apiKey": user.binance_api_key,
            "secret": user.binance_secret_key,
        }
    )

    # getting this data is a mess from binance https://dev.binance.vision/t/how-to-get-all-past-orders/1828/3
    # https://github.com/ccxt/ccxt/blob/master/examples/py/binance-fetch-all-my-trades-paginate-by-id.py
    # fetch trades. fetch_my_trades requires a symbol parameter
    # filter by: selling all stablecoins
    # getting deposits would include transfers from other systems, which may not represent real cost basis

    breakpoint()


# TODO this command needs to be cleaned up with some more options
@cli.command(short_help="Convert stablecoins to USD for purchasing")
def convert():
    user = user_for_cli()
    orders = SellStablecoinsCommand.execute(user)

    click.secho(f"\nSold {len(orders)} stablecoins", fg="green")


@cli.command(
    short_help="Buy additional tokens for your index",
    help="Buys additional tokens using purchasing currency in your exchange(s)",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["md", "csv"]),
    default="md",
    show_default=True,
    help="Output format",
)
@click.option("-d", "--dry-run", is_flag=True, help="Dry run, do not buy coins")
@click.option(
    "-p",
    "--purchase-balance",
    type=float,
    help="Dry-run with a specific amount of purchasing currency",
)
@click.option(
    "-c",
    "--convert",
    is_flag=True,
    help="Convert all stablecoin equivilents to purchasing currency. Overrides user configuration.",
)
@click.option("--cancel-orders", is_flag=True, help="Cancel all stale orders")
def buy(format, dry_run, purchase_balance, convert, cancel_orders):

    if purchase_balance:
        purchase_balance = Decimal(purchase_balance)
        bot.utils.log.debug("dry run using fake purchase balance", purchase_balance=purchase_balance)
        dry_run = True

    user = user_for_cli()

    # if user is in testmode, assume user wants dry run
    if not dry_run and not user.livemode:
        dry_run = True

    if dry_run:
        click.secho("Bot running in dry-run mode\n", fg="green")

    if convert:
        user.convert_stablecoins = True

    if cancel_orders:
        user.cancel_stale_orders = True

    if dry_run:
        user.convert_stablecoins = False
        user.cancel_stale_orders = False
        user.livemode = False

    results_by_exchange = BuyCommand.execute(user, purchase_balance)

    for exchange_result in results_by_exchange:
        exchange, purchase_balance, market_buys, completed_orders = exchange_result

        click.secho(f"\nResults for {exchange}", fg="green")
        click.secho(f"Purchasing Balance: {bot.utils.currency_format(purchase_balance)}", fg="green")

        click.echo(bot.utils.table_output_with_format(market_buys, format))

        if not market_buys:
            click.secho("\nNot enough purchasing currency to make any trades.", fg="red")
        else:
            purchased_token_list = ", ".join([order["symbol"] for order in completed_orders])
            click.secho(f"\nSuccessfully purchased: {purchased_token_list}", fg="green")


if __name__ == "__main__":
    cli()
