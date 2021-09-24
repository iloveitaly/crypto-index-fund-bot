# https://docs.pro.coinbase.com/#client-libraries
import coinbasepro as cbpro

coinbase_public_client = cbpro.PublicClient()
coinbase_exchange = coinbase_public_client.get_products()


def can_buy_in_coinbase(symbol, purchasing_currency):
    for coin in coinbase_exchange:
        if coin["base_currency"] == symbol and coin["quote_currency"] == purchasing_currency:
            return True
