import requests
import random
from time import sleep
from collections import deque

s = requests.Session()
s.headers.update({'X-API-key': 'MPWH62JM'})

MAX_GROSS_EXPOSURE  = 25000
MAX_TICKER_POSITION = {'CNR': 2000, 'RY': 8000, 'AC': 2000}

ORDER_LIMIT = 500
TICK = 0.01

QUOTE_LIFETIME_BASE = 0.12

FEES    = {'CNR': 0.01,  'RY': 0.0015, 'AC': 0.003}
REBATES = {'CNR': 0.002, 'RY': 0.0011, 'AC': 0.0001}

PRICE_HISTORY_LEN = {'CNR': 10, 'RY': 20, 'AC': 10}
price_history = {t: deque(maxlen=PRICE_HISTORY_LEN[t]) for t in ['CNR', 'RY', 'AC']}


# --------------------------------------------------
# API HELPERS
# --------------------------------------------------

def get_tick():
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']

def get_book(ticker):
    resp = s.get('http://localhost:9999/v1/securities/book', params={'ticker': ticker})
    if resp.ok:
        return resp.json()

def get_bid_ask(ticker):
    book = get_book(ticker)
    return book['bids'][0]['price'], book['asks'][0]['price']

def get_all_positions():
    resp = s.get('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        positions = {item['ticker']: item['position'] for item in book}
        net   = sum(positions.values())
        gross = sum(abs(v) for v in positions.values())
        return positions, net, gross
    return {}, 0, 0


# --------------------------------------------------
# SIGNALS
# --------------------------------------------------

def get_trend(ticker, bid, ask):
    mid = (bid + ask) / 2
    price_history[ticker].append(mid)

    if len(price_history[ticker]) < PRICE_HISTORY_LEN[ticker]:
        return 0

    oldest = price_history[ticker][0]
    newest = price_history[ticker][-1]
    avg    = sum(price_history[ticker]) / len(price_history[ticker])

    momentum = (newest - oldest) / avg
    return max(-1, min(1, momentum / 0.0005))


def get_book_imbalance(ticker):
    book = get_book(ticker)
    bid_vol = sum([b['quantity'] for b in book['bids'][:3]])
    ask_vol = sum([a['quantity'] for a in book['asks'][:3]])

    total = bid_vol + ask_vol
    if total == 0:
        return 0

    return (bid_vol - ask_vol) / total


# --------------------------------------------------
# CORE LOGIC
# --------------------------------------------------

def min_profitable_spread(ticker):
    fee = FEES[ticker]
    rebate = REBATES[ticker]
    return 2 * fee - 2 * rebate + 0.002


def calculate_quotes(bid, ask, position, signal, ticker):
    spread = ask - bid
    max_pos = MAX_TICKER_POSITION[ticker]

    # Nonlinear inventory penalty
    inv_penalty = (position / max_pos) ** 3
    net_signal  = signal - inv_penalty

    # Quoting mode selection
    if spread > 3 * TICK:
        mode = "JOIN"
    elif abs(signal) > 0.4:
        mode = "FADE"
    else:
        mode = "PASSIVE"

    if mode == "PASSIVE":
        buy_price  = bid
        sell_price = ask

    elif mode == "JOIN":
        buy_price  = bid + TICK
        sell_price = ask - TICK

    else:  # FADE
        buy_price  = bid - TICK
        sell_price = ask + TICK

    # Skew prices
    buy_price  -= net_signal * TICK
    sell_price -= net_signal * TICK

    buy_price  = round(buy_price, 2)
    sell_price = round(sell_price, 2)

    if buy_price >= sell_price:
        buy_price  = bid
        sell_price = ask

    return buy_price, sell_price


def calculate_size(position, base_size, ticker):
    max_pos = MAX_TICKER_POSITION[ticker]
    inv_ratio = abs(position) / max_pos

    # Reduce size as inventory increases
    size_factor = max(0.2, 1 - inv_ratio)

    return int(max(100, min(ORDER_LIMIT, base_size * size_factor)))


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def main():

    ticker_list = ['CNR', 'RY', 'AC']

    while True:

        tick, status = get_tick()
        if status != "ACTIVE":
            break

        positions, net_position, gross_position = get_all_positions()

        # Continuous risk constraint
        if gross_position > MAX_GROSS_EXPOSURE * 0.95:
            for t in ticker_list:
                s.post('http://localhost:9999/v1/commands/cancel', params={'ticker': t})
            continue

        # Allocate capital by opportunity
        spreads = {}
        for t in ticker_list:
            bid, ask = get_bid_ask(t)
            spreads[t] = ask - bid

        total_spread = sum(max(spreads[t], 0.001) for t in ticker_list)
        capital = MAX_GROSS_EXPOSURE - gross_position

        for t in ticker_list:

            bid, ask = get_bid_ask(t)
            spread = ask - bid

            if spread < min_profitable_spread(t):
                continue

            trend = get_trend(t, bid, ask)
            pressure = get_book_imbalance(t)

            signal = 0.6 * trend + 0.4 * pressure

            pos = positions.get(t, 0)

            base_size = capital * (spread / total_spread) / 2
            size = calculate_size(pos, base_size, t)

            buy_price, sell_price = calculate_quotes(bid, ask, pos, signal, t)

            max_pos = MAX_TICKER_POSITION[t]

            if pos < max_pos and gross_position < MAX_GROSS_EXPOSURE:
                s.post('http://localhost:9999/v1/orders', params={
                    'ticker': t,
                    'type': 'LIMIT',
                    'quantity': size,
                    'price': buy_price,
                    'action': 'BUY'
                })

            if pos > -max_pos and gross_position < MAX_GROSS_EXPOSURE:
                s.post('http://localhost:9999/v1/orders', params={
                    'ticker': t,
                    'type': 'LIMIT',
                    'quantity': size,
                    'price': sell_price,
                    'action': 'SELL'
                })

        sleep(QUOTE_LIFETIME_BASE + random.random() * 0.08)

        for t in ticker_list:
            s.post('http://localhost:9999/v1/commands/cancel', params={'ticker': t})


if __name__ == '__main__':
    main()
