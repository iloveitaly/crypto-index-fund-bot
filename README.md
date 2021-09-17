# Crypto Index Fund Bot

A bot to build your own index fund of cryptocurrencies using dollar-cost averaging.

There are [bots](https://allcryptobots.com) out there that do this, so why build another? They are missing key features that I wanted:

* Never sell any tokens. Instead, rebalance using USD deposits. ([HodlBot](https://www.hodlbot.io) can't do this)
* Control which tokens are treated as deposits. Specifically, only use USD deposits for purchasing new currencies. ([Shrimpy](https://www.shrimpy.io) can't do this)
* Build a cross-chain index (otherwise [TokenSets](https://www.tokensets.com) would have been perfect)
* When new deposits come in, asset purchases should be prioritized by:
  * New tokens that aren't held at all ([Shrimpy](https://www.shrimpy.io) can't do this)
  * Tokens whose value has dropped the most over the last month (not aware of any bot that does this)
  * Tokens whose allocation is below target (nearly all bots do this)
* Control the minimum and maximum purchase size for new crypto orders. Most bots keep buying the same token over attempting to reach the correct target allocation. I want to distribute new USD deposits over a range of tokens.
* Represent assets held outside of the bot-managed exchange(s) in the index (not aware of any bot that does this).
* Ability to exclude certain types of tokens, like stable coins or wrapped tokens (most existing bots allow you to do this manually).
* Ability to exclude specific tokens from the index completely (most existing bots allow for this).
* Build a cross-exchange index. Binance and Coinbase are great, but they have a limited set of tokens. I'd like to build an index across multiple exchanges, optimizing for token purchases in each exchange that can't be made in the other (for instance, NEXO isn't available in Binance or CoinBase, but is available in HitBTC). I'm not aware of any bot that does this.
* Convert stablecoin balance to USD for puchasing (Shrimpy does this).
* Ability to deprioritize (buy last) but still hold certain tokens
* Open source so I can audit and understand the nuances of the bot.

Here are some features I *didn't* want that I could imagine others would like:

* Customizing individual index weights of specific coins
* Rebalancing by selling existing tokens
* Using a DEX vs a centralized exchange

Also, [I wanted to learn python](https://mikebian.co/building-a-crypto-index-bot-and-learning-python/), and this was a perfect [learning project.](http://mikebian.co/my-process-for-intentional-learning/) Please excuse any beginner-python code (and submit PRs to fix!).

## Install

This project uses [asdf](https://asdf-vm.com/) to install required runtime versions. `asdf install` will source versions from `.tool-versions` for you.

After installing python and poetry, install python dependencies:

```shell
poetry install
```

You'll need some API keys for the bot to work. First, copy the env template:

```shell
cp .env-example .env
```

Then grab API keys:

* [Binance US.](http://mikebian.co/binance) Right now, this is the only supported exchange. Generate API keys without withdrawal permissions but with ordering permissions.
* [CoinMarketCap.](https://coinmarketcap.com/api/) Used for calculating the cap-weighted index.

If you have externally-held assets, you'll want to represent them in `external_portfolio.json`:

```shell
cp external_portfolio_example.json external_portfolio.json
```

Then, you'll be ready to jump into a venv and start playing:

```shell
poetry shell
python main.py
```

## Command Line Usage

Right now, there are some variables that are hardcoded into the `User` class that you may want to change. Assuming you've taken a look at the `User` options *and* configured `.env` you can run `python main.py --help` to get the following information:

```
Usage: main.py [OPTIONS] COMMAND [ARGS]...

  Tool for building your own crypto index fund.

Options:
  -v, --verbose  Enables verbose mode.
  --help         Show this message and exit.

Commands:
  analyze    Analyize configured exchanges
  buy        Buy additional tokens for your index
  index      Print index by market cap
  portfolio  Print current portfolio with targets
```

Some examples:

```shell
python main.py index

# To view your current portfolio (including your externally held assets) with target allocations
# _and_ additional assets with targets that the bot will purchase towards.
python main.py portfolio --format=csv

python main.py buy --purchase-balance=200

python main.py buy --dry-run
```

This is the command you'll want to setup on a cron job:

```shell
python main.py buy
```

## Single-user Deployment

You can use docker to deploy a single-user instance of this bot to a VPS or a local machine like a Raspberry Pi.

```
docker build -t crypto-index-fund-bot .
docker run -d --env-file .env crypto-index-fund-bot
```

In single-user mode, all configuration is set via environment variables.
There is a `SCHEDULE` variable which you can use to configure how often the account is checked for new deposits.

`external_portfolio.json` is copied into the container if it exists locally.

## Multi-user Deployment

In addition to sourcing the user configuration from `.env` and running the bot in single-user mode, you can run the bot in multi-user mode. If you do this:

* Django is loaded
* Redis and postgres services are required
* Celery is used to check users accounts on a recurring basis

There's a `docker-compose` which you can use to easily setup ths bot multi-user mode:

```shell
docker compose up -d
docker compose run worker python manage.py sqlcreate
docker compose run worker python manage.py migrate

# now that the database is setup, restart the worker to pick up on the new schema
docker compose restart worker

# after the application is setup you can run a python shell
docker compose run worker bash
python manage.py shell_plus
```

Here's how to create a new user once you are in the django shell:

```
User.objects.create(name="peter pan", binance_api_key="...", binance_secret_key="...")
```

If you want to update your deployment to the latest version:

```shell
docker compose build
docker compose up -d
```

## Testing

A separate database is used for the test environment. To create it and setup the schema:

```shell
poetry shell
DJANGO_SETTINGS_MODULE="botweb.settings.test" python manage.py sqlcreate
DJANGO_SETTINGS_MODULE="botweb.settings.test" python manage.py migrate
```

Then, you can run tests:

```shell
pytest
```

Note that VCR is used to record interactions for some of the tests. If tests are failing, you may need to re-record a test:

```shell
pytest -k 'test_test_name' --record-mode=rewrite
```

## Implementation Details

### Index Strategies

* Market Index. This is the default strategy.
* Sqrt Market Index. Reduces the weight that the largest entries in an index have. [Here's a good overview](https://help.shrimpy.io/hc/en-us/articles/1260803099290-Shrimpy-Index-Creator-Weighting) of this strategy.
* SME Index. _Not yet implemented._

### Market orders

On many exchanges a market order pays higher fees than limit orders. But Binance fees are the same whether you're the maker or the taker. For simplicity, this bot just places instantly-fulfilled market orders. There's usually sufficient liquidity to assume your order will be filled without the price moving much in the milliseconds it takes to check the market and then place the order.

The only way to reduce Binance fees is to hold their BNB token in your account (currently 0.1% fees become 0.075%).

### Limit Orders

_WIP limit order documentation. Right now, there is a limit order strategy, but we don't auto-cancel them after a certain period of time_

If a limit order is not filled, by default it [remains open indefinitely.](https://academy.binance.com/en/articles/understanding-the-different-order-types) This bot will automatically cancel any open limit orders that have not been filled based on the user configuration. The cancellation process does not differentiate between orders created by the bot and orders created by the user.

The bot will *not* submit an order for a token that has an existing open order.

### Order Minimums

Exchanges specify a minimum buy order value for each crypto (i.e. `minNotional` in Binance). Let's say you're looking to buy equal amounts of 10 different cryptos and only want to spend 0.005 BTC altogether, which would result in 0.0005 BTC of each token being purchased.

However, let's say the `minNotional` for BTC orders is 0.001; an exchange will not let you place an order whose value is smaller than that. In this case, we will ensure the minimum order amount is satisfied even if it means exceeding your target allocation (this would only happen small small amounts of total crypto holdings).

### Crypto Exchange Requirements

_WIP requirements for adding support for new exchages. Right now only binance is supported_

Hard requirements:

* Ability to determine the price and amount of all assets
* Published order minimums in purchasing currency (i.e. 10 USD)
* Published order minimums for the purchased token (i.e. 10 XLM)
* Ability to make a market and limit order

Nice to have:

* Ability to submit orders in the purchasing currency instead of tokens quantities
* Specify an exact time for an order to expire, rather than just GTC.
* Ability to deposit a recurring amount, in USD rather than a stablecoin (which requires fees to be usable for purchases)

## Related & Alternative Systems

### Open Source

* https://github.com/kdmukai/binance_bbb the primary inspiration for this bot.
* https://github.com/benmarten/CryptoETF generates a target index but doesn't automatically make purchases
* https://github.com/nazjunaid/MyCryptoIndexFund another more user-friendly index generator that doesn't make any purchases
* https://github.com/danrue/crypto-indexer/ same as above, but has been dead for a long time.
* https://github.com/aboutlo/crypto-index-fund google sheets based option
* https://github.com/jackkinsella/crypto-index rails-based trading bot. Looked advanced (too complex for what I'm trying to do), but has been dead for a very long time.
* https://github.com/leoncvlt/cryptodex recently developed
* https://github.com/askmike/gekko

### Paid

* https://cryptoindex.com Very interesting product, but looks too advanced for what I was trying to do.
* https://www.hodlbot.io. Interesting product, but looks abandoned. Doesn't support DCA, it will sell your assets to rebalance.
* https://www.shrimpy.io. Best bot that I could find. They have [an advanced DCA product](https://help.shrimpy.io/hc/en-us/articles/1260803098690-Dollar-Cost-Averaging-DCA-in-Shrimpy) which only reallocates new deposits to the account.
* https://www.tokensets.com. Really interesting solution to this problem using smart contracts. Only supports EC20 tokens.

### Funds

* https://crypto20.com/en/
* https://www.bitwiseinvestments.com/funds

## Disclaimer

I am not a qualified licensed investment advisor and I don't have any professional finance experience. This tool neither is, nor should be construed as an offer, solicitation, or recommendation to buy or sell any cryptocurrencies assets. Use it at your own risk.
