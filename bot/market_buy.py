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
from .utils import entry_key_with_symbol, log


# TODO this method is way too big, we should break it up
def calculate_market_buy_preferences(
    target_index: t.List[CryptoData],
    merged_portfolio: t.List[CryptoBalance],
    deprioritized_coins: t.List[str],
    exchange: SupportedExchanges,
    user: User,
) -> t.List[CryptoData]:
    """
    Buying priority:

    1. What hasn't been explicitly deprioritized by the user (optional, user configurable)
    2. What has exceeded the allocation drift percentage (optional, user configurable)
    3. What has exceeded the allocation drift multiple (optional, user configurable)
    4. A token that is not currently held at all
    5. Buying whatever has dropped the most
    6. Buying what has the most % delta, on an absolute basis, from the target

    Filters applied:

    1. Remove tokens that have exceeded their target allocations
    2. If multiple exchanges are being used, and the exchange is not primary, remove tokens that are available on another exchange (user configurable)
    3. Remove tokens that contain excluded filters (user configurable)
    4. Remove tokens that are not explicitly excluded (user configurable)
    """

    log.info("calculating market buy preferences", target_index=len(target_index), current_portfolio=len(merged_portfolio))

    def portfolio_entry_key_for_coin(portfolio: t.List[CryptoBalance], coin_data: CryptoData, key: str) -> t.Optional[t.Any]:
        return next((balance[key] for balance in portfolio if balance["symbol"] == coin_data["symbol"]), None)

    # for loops instead of list comprehensions because we want to log and debug various details

    coins_below_index_target: t.List[CryptoData] = []

    # TODO we should extract out the for loops into a filter function

    # first, let's exclude all coins that we've exceeded target on
    for coin_data in target_index:
        current_percentage = portfolio_entry_key_for_coin(merged_portfolio, coin_data, "percentage") or 0
        # next((balance["percentage"] for balance in merged_portfolio if balance["symbol"] == coin_data["symbol"]), 0)

        if current_percentage < coin_data["percentage"]:
            coins_below_index_target.append(coin_data)
        else:
            log.debug("coin exceeding target, skipping", symbol=coin_data["symbol"], percentage=current_percentage, target=coin_data["percentage"])

    coins_unique_to_exchange: t.List[CryptoData] = []

    # if this is a secondary exchange, we want to only buy tokens that are unique to this exchange
    # this filter also ensures that the coin can be purchased in the current exchange
    # TODO should we give users the option to prioritize coins unique to this exchange but not making buying them the only option?
    for coin_data in coins_below_index_target:
        supported_exchanges_for_coin = exchanges.exchanges_with_symbol(coin_data["symbol"], user.purchasing_currency)

        # purchase this token if (a) we are processing the primary exchange or (b) it's only available on this exchange
        if exchange in supported_exchanges_for_coin and (user.is_primary_exchange(exchange) or [exchange] == supported_exchanges_for_coin):
            coins_unique_to_exchange.append(coin_data)
        else:
            log.debug("coin not unique to exchange, skipping", symbol=coin_data["symbol"], exchange=exchange)

    # TODO pretty sure this sort is nearly useless given the order sorts below
    # TODO think about grouping drops into tranches so the above sort isn't completely useless
    # sort by coins with the largest allocation delta
    sorted_by_largest_target_delta = sorted(
        coins_unique_to_exchange,
        key=lambda coin_data: next((balance["percentage"] for balance in merged_portfolio if balance["symbol"] == coin_data["symbol"]), Decimal(0))
        - coin_data["percentage"],
    )

    # prioritize coins with the highest drop/lowest gains in the last 30d
    # TODO maybe we should apply some filter here? Only sort when change exceeds a treshold?

    sorted_by_largest_recent_drop = sorted(
        sorted_by_largest_target_delta,
        # TODO should we use 7d change vs 30?
        # TODO is the sort order here correct?
        key=lambda coin_data: coin_data["change_30d"],
    )

    # prioritize tokens we don't own yet
    # previously, in this logic, coins with holdings below the minimum purchase amount were considered unowned
    # instead of being prioritized here, they will be prioritized in the (optional) `allocation_drift_multiple_limit`
    # filtering by the minimum ownership amount would cause purchases to be made against tokens which are not as off
    # from a relative or absolute percentage basis as other tokens
    symbols_in_current_allocation = [item["symbol"] for item in merged_portfolio]

    def is_token_unowned(coin_data: CryptoData) -> int:
        if coin_data["symbol"] not in symbols_in_current_allocation:
            log.debug("coin not in current allocation or does not exceed the minimum purchase amount, prioritizing", symbol=coin_data["symbol"])
            return 0

        return 1

    sorted_by_unowned_coins = sorted(sorted_by_largest_recent_drop, key=is_token_unowned)

    # prioritize tokens that either:
    #   - are not owned or
    #   - our target allocation is off by a user-specified factor (defaults to five)
    #
    # some notes:
    #   - by returning zero we are holding previous sorting constant
    #   - previously, we only prioritized tokens with >1% market cap, but I decided this is not a good strategy
    #     if allocation is off on a smaller token, we want to prioritize it so we can rebalance before the cost
    #     of fully rebalancing gets too high.

    def should_token_be_treated_as_unowned(coin_data: CryptoData) -> int:
        target_percentage = coin_data["percentage"]

        # TODO why isn't this returning the correct typing overloads?
        current_percentage = t.cast(Decimal, entry_key_with_symbol(merged_portfolio, coin_data, "percentage"))

        # if don't special case unowned coins, then we'll most likely prioritize other coins under the target multiple
        # above new coins, which is not something I want to do. Getting some exposer to new coins is a high priority
        # so we want to prioritize unowned tokens as marginally owned (0.01)
        if current_percentage is None:
            current_percentage = Decimal("0.01")

        # nil value is checked before this function is passed to `sort`, which is why we can safely cast
        allocation_drift_multiple_limit = t.cast(int, user.allocation_drift_multiple_limit)

        # if the current allocation is off by a user-defined factor, prioritize it
        # note that this is prioritized by a relative % factor, not an absolute %
        # for absolute % prioritization, use `allocation_drift_percentage_limit`
        current_allocation_multiple = target_percentage / current_percentage
        if current_allocation_multiple > allocation_drift_multiple_limit:
            log.debug(
                "allocation percentage drift multiple exceeds user-specified percentage, prioritizing",
                symbol=coin_data["symbol"],
                drift=current_allocation_multiple,
            )
            return int(current_allocation_multiple) * -1

        return 0

    if user.allocation_drift_multiple_limit:
        sorted_by_large_market_cap_coins = sorted(sorted_by_unowned_coins, key=should_token_be_treated_as_unowned)
    else:
        sorted_by_large_market_cap_coins = sorted_by_unowned_coins

    def does_token_drift_percentage_limit(coin_data: CryptoData) -> int:
        current_percentage = portfolio_entry_key_for_coin(merged_portfolio, coin_data, "percentage")
        target_percentage = coin_data["percentage"]

        # nil value is checked before this function is passed to `sort`, which is why we can safely cast
        allocation_drift_percentage_limit = t.cast(int, user.allocation_drift_percentage_limit)

        if not current_percentage:
            return 0

        percentage_delta = target_percentage - current_percentage
        if percentage_delta > allocation_drift_percentage_limit:
            log.debug("allocation drift percentage exceeded, prioritizing", symbol=coin_data["symbol"], drift=percentage_delta)
            return -1 * int(percentage_delta)

        return 0

    if user.allocation_drift_percentage_limit:
        sorted_by_percentage_drift_prioritization = sorted(sorted_by_large_market_cap_coins, key=does_token_drift_percentage_limit)
    else:
        sorted_by_percentage_drift_prioritization = sorted_by_large_market_cap_coins

    def is_coin_deprioritized_by_user(coin_data: CryptoData) -> int:
        if coin_data["symbol"] in deprioritized_coins:
            log.debug("coin is in user's deprioritized list, deprioritized", symbol=coin_data["symbol"])
            return 1

        return 0

    # last, but not least, let's respect the user's preference for deprioritizing coins
    sorted_by_deprioritized_coins = sorted(sorted_by_percentage_drift_prioritization, key=is_coin_deprioritized_by_user)

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
    # TODO the `sum` typing definitions are incorrect, this should return a decimal
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
    symbols_of_open_orders = [order["symbol"] for order in existing_orders]

    for coin in sorted_buy_preferences:
        # TODO may make sense in the future to check the purchase amount and adjust the expected
        if coin["symbol"] in symbols_of_open_orders:
            # TODO add current order information to logs
            log.info("already have an open order for this coin", coin=coin)
            continue

        if not exchanges.is_trading_active_for_coin_in_exchange(exchange, coin["symbol"], user.purchasing_currency):
            continue

        coin_portfolio_info = entry_key_with_symbol(target_portfolio, coin, None)
        assert coin_portfolio_info is not None

        # calculate the maximum amount we could purchase based on the target allocation and current portfolio value
        # percentage is not expressed in a < 1 float, so we need to convert it
        absolute_target_amount = coin_portfolio_info["percentage"] / 100 * portfolio_total
        current_amount = t.cast(Decimal, entry_key_with_symbol(merged_portfolio, coin, "usd_total") or Decimal(0))
        target_amount = absolute_target_amount - current_amount

        purchase_amount = purchase_total

        # make sure purchase total will not overflow the target allocation, or the user specified maximum
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
