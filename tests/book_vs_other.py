# This program fires off multiple randomly generated orders at 2 different servers, and compares
# the quotes that result. One of these servers could be the official test server, though other
# people might place orders on it at the same time.

import random
import time

import stockfighter_minimal as sf

API_URL_1 = "http://127.0.0.1:8005/ob/api/"
API_KEY_1 = "fixme"

API_URL_2 = "http://127.0.0.1:8000/ob/api/"
API_KEY_2 = "fixme"

ACCOUNT_1 = "SOMEONE"
VENUE_1 = "OBEX"
SYMBOL_1 = "NYC"

ACCOUNT_2 = "EXB123456"
VENUE_2 = "TESTEX"
SYMBOL_2 = "FOOBAR"

TEST_SIZE = 3000
SEED = 314778


random.seed(SEED)
INFO = sf.Order()


def set_from_account_1(order):
    order.account = ACCOUNT_1
    order.venue = VENUE_1
    order.symbol = SYMBOL_1
    sf.change_api_key(API_KEY_1)
    sf.set_web_url(API_URL_1)

def set_from_account_2(order):
    order.account = ACCOUNT_2
    order.venue = VENUE_2
    order.symbol = SYMBOL_2
    sf.change_api_key(API_KEY_2)
    sf.set_web_url(API_URL_2)

def clear_the_books():
    global INFO
    
    INFO.qty = 999999
    INFO.orderType = "market"
    INFO.direction = "buy"
    INFO.price = 1

    set_from_account_1(INFO)
    sf.execute(INFO)
    set_from_account_2(INFO)
    sf.execute(INFO)

    INFO.direction = "sell"

    set_from_account_1(INFO)
    sf.execute(INFO)
    set_from_account_2(INFO)
    sf.execute(INFO)

    # Set the last price and size...

    INFO.orderType = "limit"
    INFO.price = 5000
    INFO.qty = 50
    INFO.direction = "sell"

    set_from_account_1(INFO)
    sf.execute(INFO)
    set_from_account_2(INFO)
    sf.execute(INFO)

    INFO.direction = "buy"

    set_from_account_1(INFO)
    sf.execute(INFO)
    set_from_account_2(INFO)
    sf.execute(INFO)



clear_the_books()

discrepancies = 0


for n in range(TEST_SIZE):
    INFO.price = random.randint(1, 10)
    INFO.qty = random.randint(1, 10)
    INFO.direction = random.choice(["buy", "sell"])
    INFO.orderType = random.choice(["limit", "limit", "limit", "limit", "market", "immediate-or-cancel", "fill-or-kill"])
    
    set_from_account_1(INFO)
    res1 = sf.execute(INFO)
    id1 = res1["id"]
    if n == 0:
        first_id_1 = id1
    if n == TEST_SIZE - 1:
        last_id_1 = id1
    q1 = sf.quote(INFO.venue, INFO.symbol)
    o1 = sf.orderbook(INFO.venue, INFO.symbol)
        
    set_from_account_2(INFO)
    res2 = sf.execute(INFO)
    id2 = res2["id"]
    if n == 0:
        first_id_2 = id2
    if n == TEST_SIZE - 1:
        last_id_2 = id2
    q2 = sf.quote(INFO.venue, INFO.symbol)
    o2 = sf.orderbook(INFO.venue, INFO.symbol)
    
    print("IDs (adjusted, should match): {}, {} ----- {} {} @ {} ({})".format(id1 - first_id_1, id2 - first_id_2, INFO.direction, INFO.qty, INFO.price, INFO.orderType))
    
    bids_match = False
    asks_match = False
    if o1["bids"] == o2["bids"]:
        bids_match = True
    if o1["asks"] == o2["asks"]:
        asks_match = True
    if (not o1["bids"]) and (not o2["bids"]):
        bids_match = True
    if (not o1["asks"]) and (not o2["asks"]):
        asks_match = True
    
    if bids_match and asks_match:
        print("Books MATCH")
    else:
        discrepancies += 1
        print(o1["bids"], o1["asks"])
        print(o2["bids"], o2["asks"])
    
    results_match = True
    for field in ("direction", "originalQty", "price", "totalFilled", "qty", "open"):
        if field not in res1:
            print("{} missing from RESULT of order 1".format(field))
            print(res1)
        if field not in res2:
            print("{} missing from RESULT of order 2".format(field))
            print(res2)
        try:
            if res1[field] != res2[field]:
                results_match = False
                print("ORDER RESULT: {}: {} vs {}".format(field, res1[field], res2[field]))
        except KeyError:
            if field in res1 or field in res2:
                print("{} missing from one result.".format(field))
                discrepancies += 1
    
    if results_match:
        print("Results MATCH", end = " --- ")
        fills = res1["fills"]
        for fill in fills:  
            print({"price" : fill["price"], "qty" : fill["qty"]}, end = "")
        print()
    else:
        discrepancies += 1
    
    quotes_match = True
    for field in ("ask", "askSize", "askDepth", "bid", "bidSize", "bidDepth", "last", "lastSize"):
        try:
            if q1[field] != q2[field]:
                print("QUOTE: {}: {} vs {}".format(field, q1[field], q2[field]))
                discrepancies += 1
                quotes_match = False
        except KeyError:
            if field in q1 or field in q2:
                print("{} missing from one quote.".format(field))
                discrepancies += 1
    
    if quotes_match:
        print("Quotes MATCH")
    
    # Randomly cancel a slightly old order with p = 33%
    
    if random.choice([True, False, False]):
        set_from_account_1(INFO)
        c1 = sf.cancel(INFO.venue, INFO.symbol, id1 - 5)
        set_from_account_2(INFO)
        c2 = sf.cancel(INFO.venue, INFO.symbol, id2 - 5)
        
        print("\nIssued a cancel.")

    print("\n{} discrepancies.\n".format(discrepancies))
    print()
    # time.sleep(0.1)

print("TEST_SIZE =", TEST_SIZE)
print("SEED =", SEED)
print()
print("Discrepancies:", discrepancies)

input()

