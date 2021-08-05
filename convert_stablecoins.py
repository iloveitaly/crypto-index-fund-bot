from utils import log
from user import User
from exchanges import binance_portfolio, binance_normalize_purchase_amount, binance_purchase_minimum

# convert all stablecoins of the purchasing currency into the purchasing currency so we can use it
# in binance, you need to purchase in USD and cannot purchase most currencies from a stablecoin
def convert_stablecoins(user: User, portfolio):
  purchasing_currency = user.purchasing_currency()
  stablecoin_symbols = []

  # TODO check if currency is a stablecoin?

  if purchasing_currency == 'USD':
    stablecoin_symbols = ['USDC', 'USDT', 'BUSD']
  else:
    raise Exception("unexpected purchasing currency input")

  binance_client = user.binance_client()
  orders = []

  for balance in [balance for balance in portfolio if balance['symbol'] in stablecoin_symbols]:
    purchase_symbol = balance['symbol'] + 'USD'
    amount = balance['amount']

    if amount < binance_purchase_minimum():
      log.info("cannot convert stablecoin, not above minimum", symbol=purchase_symbol, amount=amount)
      continue

    normalized_amount = binance_normalize_purchase_amount(amount, purchase_symbol)

    # TODO binance order construction should be pulled out into a separate method

    order_params = {
      'symbol': purchase_symbol,
      'newOrderRespType': 'FULL',

      # allows us to purchase crypto in a currency of choice
      # https://dev.binance.vision/t/beginners-guide-to-quoteorderqty-market-orders/404
      'quoteOrderQty': normalized_amount,
    }

    order = binance_client.order_market_sell(**order_params)

    """
    {'clientOrderId': 'nW6LJNE8YF1R0KWVR9r1qU',
    'cummulativeQuoteQty': '84.0000',
    'executedQty': '84.00000000',
    'fills': [{'commission': '0.00020754',
                'commissionAsset': 'BNB',
                'price': '1.0000',
                'qty': '84.00000000',
                'tradeId': 191621}],
    'orderId': 9624122,
    'orderListId': -1,
    'origQty': '84.00000000',
    'price': '0.0000',
    'side': 'SELL',
    'status': 'FILLED',
    'symbol': 'USDCUSD',
    'timeInForce': 'GTC',
    'transactTime': 1626264391365,
    'type': 'MARKET'}
    """

    log.info("order completed", order_id=order["orderId"], symbol=order["symbol"])

    orders.append(order)

  return orders

if __name__ == '__main__':
  from user import user_from_env

  user = user_from_env()
  portfolio = binance_portfolio(user)
  convert_stablecoins(user, portfolio)