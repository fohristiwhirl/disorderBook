# An implementation of a Stockfighter server in Python 3
# https://github.com/fohristiwhirl/disorderBook
#
# By Stockfighter player Amtiskaw (a.k.a. Fohristiwhirl)
# With help from Medecau and cite-reader
#
# License: BSD-2-Clause (https://opensource.org/licenses/BSD-2-Clause)
#
# ---------------------------------------------------------------------------
#
# Tests show that it is the front end (i.e. dealing with sending and receiving
# http, and so on) that takes up most (90%) of the application's time.


import json
import optparse
import threading
import random
import string

try:
    from bottle import request, response, route, run
except ImportError:
    from bottle_0_12_9 import request, response, route, run     # copy in our repo

import disorderBook_book
import disorderBook_ws


all_venues = dict()         # dict: venue string ---> dict: stock string ---> OrderBook objects
current_book_count = 0

auth = dict()


# ----------------------------------------------------------------------------------------

BAD_JSON = {"ok": False, "error": "Incoming data was not valid JSON"}
BOOK_ERROR = {"ok": False, "error": "Book limit exceeded! (See command line options)"}
NO_AUTH_ERROR = {"ok": False, "error": "Server is in +authentication mode but no API key was received"}
AUTH_FAILURE = {"ok": False, "error": "Unknown account or wrong API key"}
AUTH_WEIRDFAIL = {"ok": False, "error": "Account of stored data had no associated API key (this is impossible)"}
NO_SUCH_ORDER = {"ok": False, "error": "No such order for that Exchange + Symbol combo"}
MISSING_FIELD = {"ok": False, "error": "Incoming POST was missing required field"}
URL_MISMATCH = {"ok": False, "error": "Incoming POST data disagreed with request URL"}
BAD_TYPE = {"ok": False, "error": "A value in the POST had the wrong type"}
BAD_VALUE = {"ok": False, "error": "Illegal value (usually a non-positive number)"}
DISABLED = {"ok": False, "error": "Disabled or not enabled. (See command line options)"}

# ----------------------------------------------------------------------------------------


class TooManyBooks (Exception):
    pass


class NoApiKey (Exception):
    pass


def dict_from_exception(e):
    di = dict()
    di["ok"] = False
    di["error"] = str(e)
    return di


def create_book_if_needed(venue, symbol):
    global current_book_count
    
    if venue not in all_venues:
        if opts.maxbooks > 0:
            if current_book_count + 1 > opts.maxbooks:
                raise TooManyBooks
        all_venues[venue] = dict()

    if symbol not in all_venues[venue]:
        if opts.maxbooks > 0:
            if current_book_count + 1 > opts.maxbooks:
                raise TooManyBooks
        all_venues[venue][symbol] = disorderBook_book.OrderBook(venue, symbol, opts.websockets)
        current_book_count += 1


def api_key_from_headers(headers):
    try:
        return headers.get('X-Starfighter-Authorization')
    except:
        try:
            return headers.get('X-Stockfighter-Authorization')
        except:
            raise NoApiKey

    
# ----------------------------------------------------------------------------------------

# Handlers for the various URLs. Since this is a server that must keep going at all costs,
# most things are wrapped in excessive try statements as a precaution.


@route("/ob/api/heartbeat", "GET")
def heartbeat():
    return {"ok": True, "error": ""}


@route("/ob/api/venues", "GET")
def venue_list():
    ret = dict()
    ret["ok"] = True
    ret["venues"] = [{"name": v + " Exchange", "venue": v, "state": "open"} for v in all_venues]
    return ret


@route("/ob/api/venues/<venue>/heartbeat", "GET")
def venue_heartbeat(venue):
    if venue in all_venues:
        return {"ok": True, "venue": venue}
    else:
        response.status = 404
        return {"ok": False, "error": "Venue {} does not exist (create it by using it)".format(venue)}


@route("/ob/api/venues/<venue>", "GET")
@route("/ob/api/venues/<venue>/stocks", "GET")
def stocklist(venue):
    if venue in all_venues:
        return {"ok": True, "symbols": [{"symbol": symbol, "name": symbol + " Inc"} for symbol in all_venues[venue]]}
    else:
        response.status = 404
        return {"ok": False, "error": "Venue {} does not exist (create it by using it)".format(venue)}


@route("/ob/api/venues/<venue>/stocks/<symbol>", "GET")
def orderbook(venue, symbol):

    try:
        create_book_if_needed(venue, symbol)
    except TooManyBooks:
        response.status = 400
        return BOOK_ERROR

    try:
        ret = all_venues[venue][symbol].get_book()
        assert(ret)
        return ret
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/stocks/<symbol>/quote", "GET")
def quote(venue, symbol):
    
    try:
        create_book_if_needed(venue, symbol)
    except TooManyBooks:
        response.status = 400
        return BOOK_ERROR

    try:
        ret = all_venues[venue][symbol].get_quote()
        assert(ret)
        return ret
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/stocks/<symbol>/orders/<id>", "GET")
def status(venue, symbol, id):
    
    id = int(id)
    
    try:
        create_book_if_needed(venue, symbol)
    except TooManyBooks:
        response.status = 400
        return BOOK_ERROR
    
    try:

        account = all_venues[venue][symbol].account_from_order_id(id)
        if not account:
            response.status = 404
            return NO_SUCH_ORDER

        if auth:
            try:
                apikey = api_key_from_headers(request.headers)
            except NoApiKey:
                response.status = 401
                return NO_AUTH_ERROR
        
            if account not in auth:
                response.status = 401
                return AUTH_WEIRDFAIL
    
            if auth[account] != apikey:
                response.status = 401
                return AUTH_FAILURE
    
        ret = all_venues[venue][symbol].get_status(id)
        assert(ret)
        return ret 

    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/accounts/<account>/orders", "GET")
def status_all_orders(venue, account):
    
    # This can return a stupid amount of data and is disabled by default...
    if not opts.excess:
        response.status = 403
        return DISABLED
    
    try:
    
        if auth:
            try:
                apikey = api_key_from_headers(request.headers)
            except NoApiKey:
                response.status = 401
                return NO_AUTH_ERROR

            if account not in auth:
                response.status = 401
                return AUTH_FAILURE
    
            if auth[account] != apikey:
                response.status = 401
                return AUTH_FAILURE
        
        orders = []

        if venue in all_venues:
            for bk in all_venues[venue].values():
                orders += bk.get_all_orders(account)["orders"]

        ret = dict()
        ret["ok"] = True
        ret["venue"] = venue
        ret["orders"] = orders
        return ret
    
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/accounts/<account>/stocks/<symbol>/orders", "GET")
def status_all_orders_one_stock(venue, account, symbol):

    # This can return a stupid amount of data and is disabled by default...
    if not opts.excess:
        response.status = 403
        return DISABLED

    try:
        create_book_if_needed(venue, symbol)
    except TooManyBooks:
        response.status = 400
        return BOOK_ERROR
    
    try:
    
        if auth:
            try:
                apikey = api_key_from_headers(request.headers)
            except NoApiKey:
                response.status = 401
                return NO_AUTH_ERROR

            if account not in auth:
                response.status = 401
                return AUTH_FAILURE

            if auth[account] != apikey:
                response.status = 401
                return AUTH_FAILURE

        ret = all_venues[venue][symbol].get_all_orders(account)
        assert(ret)
        return ret

    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/stocks/<symbol>/orders/<id>", "DELETE")
@route("/ob/api/venues/<venue>/stocks/<symbol>/orders/<id>/cancel", "POST")
def cancel(venue, symbol, id):

    id = int(id)

    try:
        create_book_if_needed(venue, symbol)
    except TooManyBooks:
        response.status = 400
        return BOOK_ERROR
    
    try:
    
        account = all_venues[venue][symbol].account_from_order_id(id)
        if not account:
            response.status = 404
            return NO_SUCH_ORDER
    
        if auth:
            try:
                apikey = api_key_from_headers(request.headers)
            except NoApiKey:
                response.status = 401
                return NO_AUTH_ERROR
                
            if account not in auth:
                response.status = 401
                return AUTH_WEIRDFAIL

            if auth[account] != apikey:
                response.status = 401
                return AUTH_FAILURE

        ret = all_venues[venue][symbol].cancel_order(id)
        assert(ret)
        return ret
        
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/ob/api/venues/<venue>/stocks/<symbol>/orders", "POST")
def make_order(venue, symbol):

    try:
        data = str(request.body.read(), encoding="utf-8")
        data = json.loads(data)
    except:
        response.status = 400
        return BAD_JSON

    try:
    
        # Thanks to cite-reader for the following bug-fix:
        # Match behavior of real Stockfighter: recognize both these forms
        
        if "stock" in data:
            symbol_in_data = data["stock"]
        elif "symbol" in data:
            symbol_in_data = data["symbol"]
        else:
            symbol_in_data = symbol
        
        # Note that official SF handles POSTs that lack venue and stock/symbol (using the URL instead)
        
        if "venue" in data:
            venue_in_data = data["venue"]
        else:
            venue_in_data = venue

        # Various types of faulty POST...
        
        if venue_in_data != venue or symbol_in_data != symbol:
            response.status = 400
            return URL_MISMATCH
        
        try:
            create_book_if_needed(venue, symbol)
        except TooManyBooks:
            response.status = 400
            return BOOK_ERROR
        
        if auth:
        
            try:
                account = data["account"]
            except KeyError:
                response.status = 400
                return MISSING_FIELD
        
            try:
                apikey = api_key_from_headers(request.headers)
            except NoApiKey:
                response.status = 401
                return NO_AUTH_ERROR
            
            if account not in auth:
                response.status = 401
                return AUTH_FAILURE

            if auth[account] != apikey:
                response.status = 401
                return AUTH_FAILURE

        try:
            ret = all_venues[venue][symbol].parse_order(data)
        except TypeError:
            response.status = 400
            return BAD_TYPE
        except KeyError:
            response.status = 400
            return MISSING_FIELD
        except ValueError:
            response.status = 400
            return BAD_VALUE

        assert(ret)
        return ret
        
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


# This next isn't part of the official API. FIXME? Maybe should require authentication...

@route("/ob/api/venues/<venue>/stocks/<symbol>/scores", "GET")
def scores(venue, symbol):
    
    try:
    
        if venue not in all_venues or symbol not in all_venues[venue]:
            response.status = 404
            return "<pre>No such venue/stock!</pre>"
        
        try:
            currentprice = all_venues[venue][symbol].quote["last"]
        except KeyError:
            return "<pre>No trading activity yet.</pre>"
        
        all_data = []
        
        book_obj = all_venues[venue][symbol]
        
        for account, pos in book_obj.positions.items():
            all_data.append([account, pos.cents, pos.shares, pos.minimum, pos.maximum, pos.cents + pos.shares * currentprice])
            
        all_data = sorted(all_data, key = lambda x : x[5], reverse = True)
        
        table_header = "Account         USD         Shares     Pos.min    Pos.max    NAV"
        
        result_lines = []
        for datum in all_data:        # When in "serious" (authentication) mode, don't show shares and cents
            if not auth:
                result_lines.append("{:<15} ${:<10} {:<10} {:<10} {:<10} ${:<12}".format(
                                    datum[0], datum[1] // 100, datum[2], datum[3], datum[4], datum[5] // 100))
            else:
                result_lines.append("{:<15} [hidden]    [hidden]   {:<10} {:<10} ${:<12}".format(
                                    datum[0], datum[3], datum[4], datum[5] // 100))
        
        res_string = "\n".join(result_lines)
        
        ret = "<pre>{} {}\nCurrent price: ${:.2f}\n\n{}\n{}\n\nStart time:    {}\nCurrent time:  {}</pre>".format(
                    venue, symbol, currentprice / 100, table_header, res_string, book_obj.starttime, disorderBook_book.current_timestamp())
        
        return ret
    
    except Exception as e:
        response.status = 500
        return dict_from_exception(e)


@route("/gm/levels/<level>", "POST")
def start_level(level):
    return { "account": ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10)),
             "instanceId": random.randint(0, 99999999),
             "instructions": {},
             "ok": True,
             "secondsPerTradingDay": 5,
             "venues": [ x for x in all_venues.keys()],
             "tickers": [ item for sublist in all_venues.values() for item in sublist.keys() ],
             "balances": { "USD": 0 }, }

@route("/", "GET")
@route("/ob/api/", "GET")
def home():
    return """
    <pre>
    
    disorderBook: unofficial Stockfighter server
    https://github.com/fohristiwhirl/disorderBook
    
    By Amtiskaw (Fohristiwhirl on GitHub)
    With help from cite-reader, Medecau and DanielVF
    
    Mad props to patio11 for the elegant fundamental design!
    Also inspired by eu90h's Mockfighter
    
    
    
    "patio11 used go for a good reason" -- Medecau
    </pre>
    """

# ----------------------------------------------------------------------------------------


def create_auth_records():
    global auth
    global opts
    
    with open(opts.accounts_file) as infile:
        auth = json.load(infile)


def main():
    global opts
    
    opt_parser = optparse.OptionParser()
    
    opt_parser.add_option(
        "-b", "--maxbooks",
        dest = "maxbooks",
        type = "int",
        help = "Maximum number of books (exchange/ticker combos) [default: %default]")
    opt_parser.set_defaults(maxbooks = 100)
    
    opt_parser.add_option(
        "-v", "--venue",
        dest = "default_venue",
        type = "str",
        help = "Default venue; always exists [default: %default]")
    opt_parser.set_defaults(default_venue = "TESTEX")

    opt_parser.add_option(
        "-s", "--symbol", "--stock",
        dest = "default_symbol",
        type = "str",
        help = "Default symbol; always exists on default venue [default: %default]")
    opt_parser.set_defaults(default_symbol = "FOOBAR")
    
    opt_parser.add_option(
        "-a", "--accounts",
        dest = "accounts_file",
        type = "str",
        help = "File containing JSON dict of account names mapped to their API keys [default: none]")
    opt_parser.set_defaults(accounts_file = "")

    opt_parser.add_option(
        "-p", "--port",
        dest = "port",
        type = "int",
        help = "Port [default: %default]")
    opt_parser.set_defaults(port = 8000)
    
    opt_parser.add_option(
        "-e", "--extra", "--excess",
        dest   = "excess",
        action = "store_true",
        help   = "Enable commands that can return excessive responses (all orders on venue)")
    opt_parser.set_defaults(excess = False)
    
    opt_parser.add_option(
        "-w", "--ws", "--websocket", "--websockets",
        dest   = "websockets",
        action = "store_true",
        help   = "Enable websockets")
    opt_parser.set_defaults(websockets = False)

    opt_parser.add_option(
        "--wsport", "--ws_port",
        dest = "ws_port",
        type = "int",
        help = "WebSocket Port [default: %default]")
    opt_parser.set_defaults(ws_port = 8001)
    
    opts, __ = opt_parser.parse_args()
    
    create_book_if_needed(opts.default_venue, opts.default_symbol)
    
    if opts.accounts_file:
        create_auth_records()
    
    print("disorderBook starting up on port {}".format(opts.port))
    if opts.websockets:
        print("WebSockets on port {}".format(opts.ws_port))
    
    if not auth:
        print("\n -----> Warning: running WITHOUT AUTHENTICATION! <-----\n")
    
    if opts.websockets:
        ws_thread = threading.Thread(target = disorderBook_ws.start_websockets, args = (opts.ws_port, ))
        ws_thread.start()
    
    run(host = "127.0.0.1", port = opts.port)
    

if __name__ == "__main__":
    main()
