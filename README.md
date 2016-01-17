# disorderBook
An implementation of a **[Stockfighter](http://stockfighter.io)** server in Python 3<br>
Written by Stockfighter user Amtiskaw (a.k.a. Fohristiwhirl on GitHub)

## Usage

* Run `python3 disorderBook_main.py` &nbsp; (also requires `disorderBook_book.py` to be present)
* Connect your trading bots to &nbsp; **http://127.0.0.1:8000/ob/api/** &nbsp; instead of the normal URL
* Don't use https

## Requirements

With the help of Medecau, we now use the [Bottle](http://bottlepy.org/) library for request handling; a copy of the library is included in the repo (and will be used if needed), though you could also install it with `pip install bottle`.

You might want to [set up a virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) to do your work in.

## Authentication

There is no authentication by default. If you want authentication, edit `accounts.json` to contain a list of valid users and their API keys and run `python3 disorderBook_main.py -a accounts.json` (then authentication will work in [the same way](https://starfighter.readme.io/docs/api-authentication-authorization) as on the official servers, via "X-Starfighter-Authorization" headers).

## WebSockets

Thanks to the [SimpleWebSocketServer](https://github.com/dpallot/simple-websocket-server) library, we now have WebSockets. They cause a bit of a performance hit and are disabled by default; enable with the `--websockets` command line option.

## Features

* Your bots can use whatever accounts, venues, and symbols they like
* New exchanges/stocks are created as needed when someone tries to do something on them
* Two stupid bots are included - you must start them (or many copies) manually
* Scores can be accessed at &nbsp; **/ob/api/venues/&lt;venue&gt;/stocks/&lt;symbol&gt;/scores** &nbsp; (accessing this with your bots is cheating though)

## Issues / poor design choices

* Everything persists forever; we will *eventually* run out of RAM or the CPU will get bogged down

## Non-features

* disorderBook does not serve traffic directly, except to clients on the same host
* disorderBook does not speak TLS

If you want either of these features, put it behind a reverse proxy like NGINX.

## Thanks

* patio11
* cite-reader
* Medecau
* DanielVF
* eu90h

## Experimental

An experimental version with the backend in C is [being worked on](https://github.com/fohristiwhirl/disorderCook). Sadly, this doesn't lead to the sort of speedups you might hope (the bottleneck seems to be the frontend).
