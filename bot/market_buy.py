import typing as t
from decimal import Decimal

from . import exchanges
from .data_types import (
    CryptoBalance,
    CryptoData,
    ExchangeOrder,
    MarketBuy,
    MarketBuyStrategy,
    SupportedExchanges,
)
from .user import User
from .utils import log


def calculate_market_buy_preferences(
    target_index: t.List[CryptoData],
    merged_portfolio: t.List[CryptoBalance],
    deprioritized_coins: t.List[str],
    exchange: SupportedExchanges,
    user: User,
) -> t.List[CryptoData]:

    """
    Buying priority:

    1. Buying what hasn't be deprioritized by the user
    2. Buying what's unique to this exchange
    3. Buying what has > 1% of the market cap
    4. Buying something new, as opposed to getting closer to a new allocation
    5. Buying whatever has dropped the most
    6. Buying what has the most % delta from the target

    Filter out coins that have exceeded their targets
    """

    log.info("calculating market buy preferences", target_index=len(target_index), current_portfolio=len(merged_portfolio))

    # for loops instead of list comprehensions because we want to log and debug various details

    coins_below_index_target: t.List[CryptoData] = []

    # first, let's exclude all coins that we've exceeded target on
    for coin_data in target_index:
        current_percentage = next((balance["percentage"] for balance in merged_portfolio if balance["symbol"] == coin_data["symbol"]), 0)

        if current_percentage < coin_data["percentage"]:
            coins_below_index_target.append(coin_data)
        else:
            log.debug("coin exceeding target, skipping", symbol=coin_data["symbol"], percentage=current_percentage, target=coin_data["percentage"])

    coins_unique_to_exchange: t.List[CryptoData] = []

    # if this is a secondary exchange, we want to only buy tokens that are unique to this exchange
    # TODO should we give users the option to prioritize coins unique to this exchange but not making buying them the only option?
    if not user.is_primary_exchange(exchange):
        for coin_data in coins_below_index_target:
            if [exchange] == exchanges.exchanges_with_symbol(coin_data["symbol"], user.purchasing_currency):
                coins_unique_to_exchange.append(coin_data)
            else:
                log.debug("coin not unique to exchange, skipping", symbol=coin_data["symbol"], exchange=exchange)
    else:
        coins_unique_to_exchange = coins_below_index_target

    # TODO pretty sure this sort is nearly useless given the order sorts below
    # sort by coins with the largest allocation delta
    sorted_by_largest_target_delta = sorted(
        coins_below_index_target,
        key=lambda coin_data: next((balance["percentage"] for balance in merged_portfolio if balance["symbol"] == coin_data["symbol"]), Decimal(0))
        - coin_data["percentage"],
    )

    # TODO think about grouping drops into tranches so the above sort isn't completely useless
    # prioritize coins with the highest drop/lowest gains in the last 30d
    sorted_by_largest_recent_drop = sorted(
        sorted_by_largest_target_delta,
        # TODO should we use 7d change vs 30?
        # TODO is the sort order here correct?
        key=lambda coin_data: coin_data["change_30d"],
    )

    # prioritize tokens we don't own yet
    symbols_in_current_allocation = [item["symbol"] for item in merged_portfolio]
    sorted_by_unowned_coins = sorted(
        sorted_by_largest_recent_drop, key=lambda coin_data: 1 if coin_data["symbol"] in symbols_in_current_allocation else 0
    )

    # prioritize tokens that make up > 1% of the market
    # and either (a) we don't own or (b) our target allocation is off by a factor of 6
    # why 6? It felt right based on looking at what I wanted out of my current allocation

    def should_token_be_treated_as_unowned(coin_data: CryptoData) -> int:
        if coin_data["percentage"] < 1:
            return 1

        current_percentage = next((balance["percentage"] for balance in merged_portfolio if balance["symbol"] == coin_data["symbol"]), 0)

        if current_percentage == 0:
            return 0

        current_allocation_delta = coin_data["percentage"] / current_percentage
        if current_allocation_delta > 6:
            return 0

        return 1

    sorted_by_large_market_cap_coins = sorted(sorted_by_unowned_coins, key=should_token_be_treated_as_unowned)

    # last, but not least, let's respect the user's preference for deprioritizing coins
    sorted_by_deprioritized_coins = sorted(
        sorted_by_large_market_cap_coins, key=lambda coin_data: 1 if coin_data["symbol"] in deprioritized_coins else 0
    )

    return sorted_by_deprioritized_coins


def purchasing_currency_in_portfolio(user: User, unmerged_portfolio: t.List[CryptoBalance]) -> Decimal:
    """
    Important that the portfolio here is not merged with an external portfolio representation
    or a portfolio from another exchange.
    """

    # TODO I think we just need to hold back the estimated fees here

    # ideally, we wouldn't need to have a reserve amount. However, FP math is challenging and it's easy
    # to be off a cent or two. It's easier just to reserve $1 and not deal with it. Especially for a fun project.
    reserve_amount = 1

    # in the case of USD, the amount is the total. Let's use that instead, which eliminates the need to run the portfolio
    # through various functions which ammend the data to add additional metadata used for the purchasing decisions later on
    total = sum([balance["amount"] for balance in unmerged_portfolio if balance["symbol"] == user.purchasing_currency])

    # TODO we need some sort of `max` overload to treat a decimal as a `SupportsLessThanT`
    return max(total - reserve_amount, Decimal(0))  # type: ignore


def determine_market_buys(
    user: User,
    sorted_buy_preferences: t.List[CryptoData],
    merged_portfolio: t.List[CryptoBalance],
    target_portfolio: t.List[CryptoData],
    purchase_balance: Decimal,
    exchange: SupportedExchanges,
) -> t.List[MarketBuy]:
    """
    1. Is the asset currently trading?
    2. Do we have the minimum purchase amount?
    3. Are there open orders for the asset already?
    """

    # binance fees are fixed based on account configuration (BNB amounts, etc) and cannot be pulled dynamically
    # so we don't worry or calculate these as part of our buying preference calculation
    # TODO we'll need to explore if this is different for other exchanges

    # it doesn't look like this is specified in the API, and the minimum is different
    # depending on if you are using the pro vs simple view. This is the purchasing minimum on binance
    # but not on
    exchange_purchase_minimum = exchanges.purchase_minimum(exchange)

    user_purchase_minimum = user.purchase_min
    user_purchase_maximum = user.purchase_max
    portfolio_total = sum(balance["usd_total"] for balance in merged_portfolio)

    if purchase_balance < exchange_purchase_minimum:
        log.info("not enough purchasing currency to buy anything", purchase_balance=purchase_balance)
        return []

    log.info(
        "enough purchase currency balance",
        balance=purchase_balance,
        exchange_minimum=exchange_purchase_minimum,
        user_minimum=user_purchase_minimum,
    )

    purchase_total = purchase_balance
    purchases = []

    existing_orders = exchanges.open_orders(exchange, user)
    symbols_of_existing_orders = [order["symbol"] for order in existing_orders]

    for coin in sorted_buy_preferences:
        # TODO may make sense in the future to check the purchase amount and adjust the expected
        if coin["symbol"] in symbols_of_existing_orders:
            # TODO add current order information to logs
            log.info("already have an open order for this coin", coin=coin)
            continue

        if not exchanges.is_trading_active_for_coin_in_exchange(exchange, coin["symbol"], user.purchasing_currency):
            continue

        # round up the purchase amount to the total available balance if we don't have enough to buy two tokens
        purchase_amount = purchase_total if purchase_total < exchange_purchase_minimum * 2 else user_purchase_minimum

        # percentage is not expressed in a < 1 float, so we need to convert it
        coin_portfolio_info = next((target for target in target_portfolio if target["symbol"] == coin["symbol"]))
        target_amount = coin_portfolio_info["percentage"] / 100 * portfolio_total

        # make sure purchase total will not overflow the target allocation
        purchase_amount = min(purchase_amount, target_amount, user_purchase_maximum)

        # make sure the floor purchase amount is at least the user-specific minimum
        purchase_amount = max(purchase_amount, user_purchase_minimum)

        # we need to at least buy the minimum that the exchange allows
        purchase_amount = max(exchange_purchase_minimum, purchase_amount)

        # TODO right now the minNotional filter is NOT respected since the user min is $30, which is normally higher than this value
        #      this is something we'll have to handle properly in the future
        # minimum_token_quantity_in_exchange(paired_symbol)
        # symbol_info = public_binance_client.get_symbol_info(paired_symbol)
        # tick_size = next(f['minNotional'] for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')

        if purchase_amount > purchase_total:
            log.info("not enough purchase currency balance for coin", amount=purchase_amount, balance=purchase_total, coin=coin["symbol"])
            continue

        log.info("adding purchase preference", symbol=coin["symbol"], amount=purchase_amount)

        purchases.append(
            {
                "symbol": coin["symbol"],
                # TODO should we include the paired symbol in this data structure?
                # amount in purchasing currency, not a quantity of the symbol to purchase
                "amount": purchase_amount,
            }
        )

        purchase_total -= purchase_amount

        if purchase_total <= 0:
            break

    return purchases


# https://www.binance.us/en/usercenter/wallet/money-log
def make_market_buys(user: User, market_buys: t.List[MarketBuy]) -> t.List[ExchangeOrder]:
    if not market_buys:
        return []

    purchasing_currency = user.purchasing_currency
    orders = []

    log.info("executing orders", strategy=user.buy_strategy)

    for buy in market_buys:
        symbol = buy["symbol"]
        amount = buy["amount"]

        if user.buy_strategy == MarketBuyStrategy.LIMIT:
            # TODO consider executing limit orders based on the current market orders
            #      this could ensure we don't overpay for an asset with low liquidity
            from . import limit_buy

            limit_price = limit_buy.determine_limit_price(user, symbol, purchasing_currency)

            order_quantity = Decimal(buy["amount"]) / limit_price

            order = exchanges.limit_buy(
                exchange=SupportedExchanges.BINANCE,
                user=user,
                purchasing_currency=purchasing_currency,
                symbol=symbol,
                quantity=order_quantity,
                price=limit_price,
            )
        else:  # market
            order = exchanges.market_buy(
                exchange=SupportedExchanges.BINANCE, user=user, symbol=symbol, purchasing_currency=purchasing_currency, amount=amount
            )

        orders.append(order)

    # in testmode, or in the case of an error, the result is an empty dict
    # remove this since it doesn't provide any useful information and is confusing to parse downstream
    return list(filter(None, orders))
