import requests
from time import sleep

s = requests.Session()
s.headers.update({'X-API-key': 'GORYK3O5'}) # Desktop

MAX_LONG_EXPOSURE = 25000
MAX_GROSS_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
ORDER_LIMIT = 500

TICK = 0.01


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
    
def calculate_dynamic_order_size(gross_position, ticker_list):
    """Calculate order size based on available room in gross limit"""
    
    # How much room do we have left?
    available_room = MAX_GROSS_EXPOSURE - gross_position
    
    # Safety buffer to avoid hitting limit (conservative)
    SAFETY_BUFFER = 2000
    safe_room = available_room - SAFETY_BUFFER
    
    # We're quoting all 3 tickers, each with buy AND sell
    # So we need to divide by 6 (3 tickers × 2 sides)
    num_potential_orders = len(ticker_list) * 2
    per_order_room = safe_room / num_potential_orders if num_potential_orders > 0 else 0
    
    # Take the minimum of: default order size or available room per order
    dynamic_size = min(ORDER_LIMIT, per_order_room)
    
    # Ensure we don't go negative or too small (minimum 100 shares)
    dynamic_size = max(100, int(dynamic_size))
    
    return dynamic_size

QUOTE_LIFETIME = 0.3  # seconds (tune 0.2–0.7)

def main():
    ticker_list = ['CNR','RY','AC']
    while True:
        tick, status = get_tick()
        if status != "ACTIVE":
            break

        net_position, gross_position = get_position()
        order_size = calculate_dynamic_order_size(gross_position, ticker_list)

        # 1) Place quotes for ALL tickers first (no per-ticker sleep)
        for t in ticker_list:
            bid, ask = get_bid_ask(t)
            net_position, gross_position = get_position()

            if net_position < MAX_LONG_EXPOSURE and gross_position < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params={
                    'ticker': t, 'type': 'LIMIT', 'quantity': order_size,
                    'price': bid - 0.02, 'action': 'BUY'
                })

            if net_position > MAX_SHORT_EXPOSURE and gross_position < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params={
                    'ticker': t, 'type': 'LIMIT', 'quantity': order_size,
                    'price': ask + 0.02, 'action': 'SELL'
                })

        # 2) Let quotes sit in book
        sleep(QUOTE_LIFETIME)

        # 3) Cancel for ALL tickers (prevents stale orders piling up)
        for t in ticker_list:
            s.post('http://localhost:9999/v1/commands/cancel', params={'ticker': t})


"""
def main():
    tick, status = get_tick()
    ticker_list = ['CNR','RY','AC']

    while status == 'ACTIVE': 
        
        net_position, gross_position = get_position()
        
        # Calculate dynamic order size based on available room
        order_size = calculate_dynamic_order_size(gross_position, ticker_list)

        for ticker_symbol in ticker_list:
            
            best_bid_price, best_ask_price = get_bid_ask(ticker_symbol)
            net_position, gross_position = get_position()
            
       
            if net_position < MAX_LONG_EXPOSURE and gross_position < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params = {'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': order_size, 'price': best_bid_price - 0.04, 'action': 'BUY'})
                order_id = resp.son()['order_id']
                get_order_status(order_id)
                
            if net_position > MAX_SHORT_EXPOSURE and gross_position < MAX_GROSS_EXPOSURE:
                resp = s.post('http://localhost:9999/v1/orders', params = {'ticker': ticker_symbol, 'type': 'LIMIT', 'quantity': order_size, 'price': best_ask_price + 0.04, 'action': 'SELL'})

            sleep(0.5) 
            
            # Consider varying your per order volume to fit in your available gross position limit
            # If i go over the limit, recover my reducing my positions so my algos starts trading again
            # varying the prices in my order - bid below best build, offer above the best offer
            # vary the volume of my orders base on my position for each stock - buy more when I am short
            # vary the pricing and / or volume or your orders for each ticker symbol; vary your pricing and volumes by 

            s.post('http://localhost:9999/v1/commands/cancel', params = {'ticker': ticker_symbol})

        tick, status = get_tick()
"""

if __name__ == '__main__':
    main()



