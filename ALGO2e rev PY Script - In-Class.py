import requests
from time import sleep

s = requests.Session()
s.headers.update({'X-API-key': 'GORYK3O5'}) # Desktop

MAX_LONG_EXPOSURE = 25000
MAX_GROSS_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
ORDER_LIMIT = 500

def get_tick():
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']

def get_bid_ask(ticker):
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/securities/book', params = payload)
    if resp.ok:
        book = resp.json()
        bid_side_book = book['bids']
        ask_side_book = book['asks']
        
        bid_prices_book = [item["price"] for item in bid_side_book]
        ask_prices_book = [item['price'] for item in ask_side_book]
        
        best_bid_price = bid_prices_book[0]
        best_ask_price = ask_prices_book[0]
  
        return best_bid_price, best_ask_price

def get_time_sales(ticker):
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/securities/tas', params = payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book

def get_position():
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        net_position = (book[0]['position']) + (book[1]['position']) + (book[2]['position'])
        gross_position = abs(book[0]['position']) + abs(book[1]['position']) + abs(book[2]['position'])
        return net_position, gross_position
    
def get_position_by_ticker(ticker):
    # added
    """Get position for specific ticker"""
    resp = s.get('http://localhost:9999/v1/securities')
    if resp.ok:
        securities = resp.json()
        for sec in securities:
            if sec['ticker'] == ticker:
                return sec['position']

def get_open_orders(ticker):
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/orders', params = payload)
    if resp.ok:
        orders = resp.json()
        buy_orders = [item for item in orders if item["action"] == "BUY"]
        sell_orders = [item for item in orders if item["action"] == "SELL"]
        return buy_orders, sell_orders

def get_order_status(order_id):
    resp = s.get ('http://localhost:9999/v1/orders' + '/' + str(order_id))
    if resp.ok:
        order = resp.json()
        return order['status']
    
def get_pending_exposure(ticker):
    """Calculate how much exposure is coming from unfilled orders"""
    buy_orders, sell_orders = get_open_orders(ticker)
    
    pending_buys = sum(order['quantity'] - order['quantity_filled'] 
                       for order in buy_orders)
    pending_sells = sum(order['quantity'] - order['quantity_filled'] 
                        for order in sell_orders)
    
    return pending_buys, pending_sells

def main():
    tick, status = get_tick()
    ticker_list = ['CNR','RY','AC']

    while status == 'ACTIVE': 
        
        net_position, gross_position = get_position()

        for ticker_symbol in ticker_list:
            
            best_bid_price, best_ask_price = get_bid_ask(ticker_symbol)
            pending_buys, pending_sells = get_pending_exposure(ticker_symbol)
            projected_net = net_position + pending_buys - pending_sells
            projected_gross = gross_position + pending_buys + pending_sells
            
       
            if projected_net < MAX_LONG_EXPOSURE and projected_gross < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params = {'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': ORDER_LIMIT, 'price': best_bid_price, 'action': 'BUY'})
              
            if projected_net > MAX_SHORT_EXPOSURE and projected_gross < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params = {'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': ORDER_LIMIT, 'price': best_ask_price, 'action': 'SELL'})

            sleep(0.5) 
            
            # Consider varying your per order volume to fit in your available gross position limit
            # If i go over the limit, recover my reducing my positions so my algos starts trading again
            # varying the prices in my order - bid below best build, offer above the best offer
            # vary the volume of my orders base on my position for each stock - buy more when I am short

            s.post('http://localhost:9999/v1/commands/cancel', params = {'ticker': ticker_symbol})

        tick, status = get_tick()

if __name__ == '__main__':
    main()



