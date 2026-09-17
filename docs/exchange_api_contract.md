# Exchange read-only API contract

This document defines the read-only HTTP surface for the existing SLH/CREDITS exchange engine.

- `GET /api/v1/exchange/markets`
- `GET /api/v1/exchange/orderbook`
- `GET /api/v1/exchange/trades`
- `GET /api/v1/exchange/ticker`

The API is an adapter over existing exchange state. It does not create orders, execute trades, reserve balances, or mutate exchange state.

## Market
Returns the declared `SLH/CREDITS` market.

## Order book
Returns open orders with `id`, `side`, `amount`, `price`, and `created_at`.

## Trades
Returns recorded trades in read-only form.

## Ticker
Returns the most recent recorded trade price when available; otherwise `last_price` is `null` and `has_data` is `false`.
