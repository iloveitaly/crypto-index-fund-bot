# Crypto Index Fund Bot

This is a bot which purchases a index of cryptocurrencies. A self-managed [Vanguard VTI](https://investor.vanguard.com/etf/profile/VTI) for crypto assets. [Here's a good explanation](https://avc.com/2021/11/buying-crypto-assets/) of why this is probably a good idea. It's designed to be used with a dollar-cost averaging approach, but can be used with one-time deposit as well.

There are [bots](https://allcryptobots.com) out there that do this, so why build another? There are missing features I wanted:

* Never sell any tokens. Instead, rebalance towards the target allocation using recurring deposits. ([HodlBot](https://www.hodlbot.io) can't do this)
* Control which tokens are treated as deposits. Specifically, only use USD/stablecoin deposits for purchasing new currencies. ([Shrimpy](https://www.shrimpy.io) can't do this)
* Build a cross-chain index (otherwise [TokenSets](https://www.tokensets.com), which is EC-20 only, would have been perfect)
* When new deposits come in, asset purchases should be carefully prioritized. [More info on how purchases are prioritized](#buy-prioritization)
* Control the minimum and maximum purchase size for new crypto orders. Most bots keep buying the same token over attempting to reach the correct target allocation. I want to distribute new USD deposits over a range of tokens.
* Represent assets held outside of the bot-managed exchange(s) in the index (not aware of any bot that does this).
* Ability to exclude certain types of tokens, like stable coins or wrapped tokens (most existing bots allow you to do this manually).
* Ability to exclude specific tokens from the index completely (most existing bots allow for this).
* Build a cross-exchange index. Binance and Coinbase are great, but they have a limited set of tokens. I'd like to build an index across multiple exchanges, optimizing for token purchases in each exchange that can't be made in the other (for instance, NEXO isn't available in Binance or CoinBase, but is available in HitBTC). I'm not aware of any bot that does this.
* Convert stablecoin balance to USD for purchasing (Shrimpy does this).
* Ability to deprioritize (buy last) but still hold certain tokens
* Open source so I can audit and understand the nuances of the bot.

Here are some features I *didn't* want that I could imagine others would like:

* Customizing individual index weights of specific coins
* Rebalancing by selling existing tokens
* Using a DEX vs a centralized exchange

Also, [I wanted to learn python](https://mikebian.co/building-a-crypto-index-bot-and-learning-python/) and [learn django](http://mikebian.co/lessons-learned-building-with-django-celery-and-pytest/), and this was a perfect [learning project.](http://mikebian.co/my-process-for-intentional-learning/) Please excuse any beginner-python code (and submit PRs to fix!).

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

Not all configuration options are available via the CLI or the `USER_*` env vars. Checkout `bot/user.py` for more configuration options.

## Customization Options

There are a *bunch* of configuration options available. I'm not going to document them all here, since [they are documented in-code here](https://github.com/iloveitaly/crypto-index-fund-bot/blob/85f27b18aee3a0339996a84974f26fa17fc04f07/bot/user.py#L45-L81). You can configure these preferences by using `USER_PREFERENCES` in your `.env` file.

For instance:

```shell
USER_PREFERENCES='{"allocation_drift_percentage_limit":1, "allocation_drift_multiple_limit": 4}
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
  analyze     Analyze configured exchanges
  buy         Buy additional tokens for your index
  convert     Convert stablecoins to USD for purchasing
  cost-basis  Calculate cost basis
  index       Print index by market cap
  portfolio   Print current portfolio with targets
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

## Deployment

There are lots of ways to deploy the bot. Easiest will be heroku, although it works great on a Pi.

### Heroku Deployment

I'm not running this on Heroku, so it will need a bit of work. Here are some notes on what needs to be done, feel free to submit a PR!

#### Single-user

* Repo should build just fine on heroku as-is
* You'll need a Procfile with something like `worker: python main.py buy` which is triggered via the heroku scheduler
* You'd need to figure out how to get `external_portfolio.json` in the image, or modify the `user_from_env` to parse JSON from an environment variable or something.

#### Multi-user

* You'll need a worker process modeled after `celery.sh`
* Redis + postgres would need to be configured, along with `DJANGO_SETTINGS_MODULE`

### Docker

#### Single-user Docker Deployment

You can use docker to deploy a single-user instance of this bot to a VPS or a local machine like a Raspberry Pi.

```
docker build -t crypto-index-fund-bot .
docker run -d --env-file .env crypto-index-fund-bot
```

In single-user mode, all configuration is set via environment variables.
There is a `SCHEDULE` variable which you can use to configure how often the account is checked for new deposits.

`external_portfolio.json` is copied into the container if it exists locally.

#### Multi-user Docker Deployment

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
docker compose run worker scripts/console.sh
```

Here's how to create a new user once you are in the django shell:

```python
User.objects.create(name="peter pan", binance_api_key="...", binance_secret_key="...", preferences={"livemode": True})
```

Want to trigger some jobs manually for testing?

```python
import users.celery
users.celery.initiate_user_buys.delay()
```

Want to run the CLI tools for a specific user?

```shell
docker compose run worker bash
USER_ID=10 python main.py portfolio
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

Debuggins something in particular? Probably useful to increase log level:

```shell
LOG_LEVEL=debug pytest
```

Want to break on unhandled exceptions?

```shell
pytest -s --pdb
```

## Typechecking

I like Pylance, the preferred VS Code python extension, which uses `pyright` for typchecking.

```shell
# install node either via asdf or directly
asdf install

# a specific version is required until this is fixed https://github.com/microsoft/pyright/issues/2578
npm install -g pyright@1.1.186

pyright .
```

## Linting

The linter currently doesn't pass, which is why it's not enabled on CI. You can run it here (feel free to submit PRs to get it closer to passing!):

```shell
poetry shell
pylint **/*.py
```

## Implementation Details

### Buy Prioritization

All of the buying prioritization happens in [`calculate_market_buy_preferences`](https://github.com/iloveitaly/crypto-index-fund-bot/blob/85f27b18aee3a0339996a84974f26fa17fc04f07/bot/market_buy.py#L18) which is decently documented with inline comments. I recommend taking a look if you are curious.

Basically, the logic does two things:

* Filters out tokens that are not eligible for buying
* Sorts the remaining tokens

#### Filtering

1. Remove tokens that have exceeded their target allocations
2. If multiple exchanges are being used, and the exchange is not primary, remove tokens that are available on another exchange (user configurable)
3. Remove tokens that contain excluded filters (user configurable)
4. Remove tokens that are not explicitly excluded (user configurable)

#### Sorting

1. What hasn't been explicitly deprioritized by the user (optional, user configurable)
2. What has exceeded the allocation drift percentage (optional, user configurable)
3. What has exceeded the allocation drift multiple (optional, user configurable)
4. A token that is not currently held at all
5. Buying whatever has dropped the most
6. Buying what has the most % delta, on an absolute basis, from the target

### Index Strategies

* Market Index. This is the default strategy.
* Sqrt Market Index. Reduces the weight that the largest entries in an index have. [Here's a good overview](https://help.shrimpy.io/hc/en-us/articles/1260803099290-Shrimpy-Index-Creator-Weighting) of this strategy.
* SME Index. _Not yet implemented._

### Market orders

On many exchanges a market order pays higher fees than limit orders. But Binance fees are the same whether you're the maker or the taker. For simplicity, this bot just places instantly-fulfilled market orders. There's usually sufficient liquidity to assume your order will be filled without the price moving much in the milliseconds it takes to check the market and then place the order.

The only way to reduce Binance fees is to hold their BNB token in your account (currently 0.1% fees become 0.075%).

### Limit Orders

_WIP limit order documentation. Right now, there is a limit order strategy, but it's not well thought through_

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

Some helpful exchange-specific links:

* [New binance tokens](https://support.binance.us/hc/en-us/sections/360008343893-New-Listings)

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
* https://www.bitfract.com Exchange one coin for multiple. This tool does *not* use a centralized exchange, which is really interesting. It was acquired and looks abandoned.
* https://www.alongside.xyz/ Looks new, not much info out about it. 

### Funds

* https://crypto20.com/en/
* https://www.bitwiseinvestments.com/funds

## Disclaimer

I am not a qualified licensed investment advisor and I don't have any professional finance experience. This tool neither is, nor should be construed as an offer, solicitation, or recommendation to buy or sell any cryptocurrencies assets. Use it at your own risk.
