"""Read-only market heatmap data adapter and local paper-market metrics.

Market quotes come only from a configured licensed provider. This module never
submits orders, uses brokerage credentials, stores account funds, or suggests a
personalized buy/sell action. Paper positions are browser-local in the UI.
"""
from __future__ import annotations

import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests


PROVIDER = "Twelve Data"
QUOTE_URL = "https://api.twelvedata.com/quote"
CACHE_TTL_SECONDS = 90
REQUEST_TIMEOUT = (3, 8)

# Curated heatmap universe; intentionally fixed and provider-allowlisted.
UNIVERSE = (
    {"symbol": "SPY", "name": "S&P 500 ETF", "group": "מדדי שוק", "kind": "index"},
    {"symbol": "QQQ", "name": "Nasdaq 100 ETF", "group": "מדדי שוק", "kind": "index"},
    {"symbol": "DIA", "name": "Dow Jones ETF", "group": "מדדי שוק", "kind": "index"},
    {"symbol": "IWM", "name": "Russell 2000 ETF", "group": "מדדי שוק", "kind": "index"},
    {"symbol": "XLK", "name": "Technology", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLF", "name": "Financials", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLE", "name": "Energy", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLV", "name": "Health Care", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLI", "name": "Industrials", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLY", "name": "Consumer Discretionary", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLP", "name": "Consumer Staples", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLU", "name": "Utilities", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLB", "name": "Materials", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLRE", "name": "Real Estate", "group": "סקטורים", "kind": "sector"},
    {"symbol": "XLC", "name": "Communication Services", "group": "סקטורים", "kind": "sector"},
)

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _quote_map(payload: Any) -> dict[str, dict]:
    if not isinstance(payload, dict):
        return {}
    # Twelve Data commonly responds with one object for one symbol and a
    # symbol-keyed object for multi-symbol queries. Accept only these shapes.
    if isinstance(payload.get("symbol"), str):
        return {payload["symbol"].upper(): payload}
    data = payload.get("data")
    if isinstance(data, list):
        return {
            str(row.get("symbol") or "").upper(): row
            for row in data if isinstance(row, dict) and row.get("symbol")
        }
    return {
        str(key).upper(): value
        for key, value in payload.items()
        if isinstance(value, dict) and value.get("symbol")
    }


def _normalize_quote(meta: dict, raw: dict) -> dict | None:
    price = _finite_number(raw.get("price"))
    if price is None:
        price = _finite_number(raw.get("close"))
    if price is None or price <= 0:
        return None

    pct = _finite_number(raw.get("percent_change"))
    if pct is None:
        pct = _finite_number(raw.get("change_percent"))
    if pct is None:
        change = _finite_number(raw.get("change"))
        previous_close = _finite_number(raw.get("previous_close"))
        if change is not None and previous_close is not None and previous_close > 0:
            pct = 100.0 * change / previous_close
    if pct is None or not math.isfinite(pct):
        return None

    provider_time = raw.get("datetime") or raw.get("timestamp")
    if isinstance(provider_time, (str, int, float)):
        provider_time = str(provider_time)[:40]
    else:
        provider_time = None

    change = _finite_number(raw.get("change"))
    return {
        **meta,
        "price": round(price, 6),
        "change_percent": round(pct, 4),
        "change": round(change, 6) if change is not None else None,
        "currency": str(raw.get("currency") or "USD")[:8],
        "provider_time": provider_time,
        "status": "AVAILABLE",
    }


def market_snapshot(*, force: bool = False, now: float | None = None) -> dict:
    """Return sanitized public market data, or an explicit blocked status."""
    current = time.time() if now is None else float(now)
    with _LOCK:
        cached = _CACHE.get("payload")
        if not force and isinstance(cached, dict) and current < float(_CACHE.get("expires_at") or 0):
            result = dict(cached)
            result["cache"] = "HIT"
            return result

    api_key = str(os.getenv("TWELVEDATA_API_KEY", "") or "").strip()
    if not api_key:
        return {
            "status": "DATA_PROVIDER_NOT_CONFIGURED",
            "provider": PROVIDER,
            "tiles": [],
            "missing_symbols": [item["symbol"] for item in UNIVERSE],
            "fetched_at_utc": None,
            "cache": "MISS",
            "reason": "Set TWELVEDATA_API_KEY in the server environment; never put it in browser code.",
            "paper_only": True,
        }

    try:
        response = requests.get(
            QUOTE_URL,
            params={"symbol": ",".join(item["symbol"] for item in UNIVERSE)},
            headers={"Authorization": "apikey " + api_key, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise ValueError("PROVIDER_HTTP_ERROR")
        raw_payload = response.json()
        if not isinstance(raw_payload, (dict, list)):
            raise ValueError("PROVIDER_RESPONSE_INVALID")
        if isinstance(raw_payload, dict) and (
            raw_payload.get("status") == "error" or raw_payload.get("code")
        ):
            raise ValueError("PROVIDER_REJECTED_REQUEST")
        quotes = _quote_map(raw_payload)
        tiles = []
        missing = []
        for meta in UNIVERSE:
            quote = quotes.get(meta["symbol"])
            normalized = _normalize_quote(meta, quote) if isinstance(quote, dict) else None
            if normalized is None:
                missing.append(meta["symbol"])
            else:
                tiles.append(normalized)
        if not tiles:
            raise ValueError("NO_VALID_QUOTES")
        fetched_at = datetime.now(timezone.utc).isoformat()
        result = {
            "status": "AVAILABLE" if not missing else "PARTIAL",
            "provider": PROVIDER,
            "tiles": tiles,
            "missing_symbols": missing,
            "fetched_at_utc": fetched_at,
            "cache": "MISS",
            "paper_only": True,
            "data_disclaimer": "Prices and timestamps are provider-reported and may be delayed; confirm licence/entitlements before public display.",
        }
        with _LOCK:
            _CACHE["payload"] = dict(result)
            _CACHE["expires_at"] = current + CACHE_TTL_SECONDS
        return result
    except Exception as exc:
        # Never return the provider body, URL query, credential, or raw exception.
        return {
            "status": "PROVIDER_UNAVAILABLE",
            "provider": PROVIDER,
            "tiles": [],
            "missing_symbols": [item["symbol"] for item in UNIVERSE],
            "fetched_at_utc": None,
            "cache": "MISS",
            "reason": type(exc).__name__ if type(exc).__name__ in {"Timeout", "ConnectionError"} else "QUOTE_DATA_UNAVAILABLE",
            "paper_only": True,
        }


def market_lab_summary(snapshot: dict) -> dict:
    """Descriptive cross-sectional summary, not a buy/sell recommendation."""
    tiles = snapshot.get("tiles") if isinstance(snapshot, dict) else None
    valid = [tile for tile in tiles if isinstance(tile, dict) and _finite_number(tile.get("change_percent")) is not None] if isinstance(tiles, list) else []
    if not valid:
        return {"status": "UNKNOWN", "top_relative_move": None, "bottom_relative_move": None, "average_change_percent": None}
    ordered = sorted(valid, key=lambda tile: float(tile["change_percent"]))
    return {
        "status": "DESCRIPTIVE_ONLY",
        "top_relative_move": {"symbol": ordered[-1]["symbol"], "change_percent": ordered[-1]["change_percent"]},
        "bottom_relative_move": {"symbol": ordered[0]["symbol"], "change_percent": ordered[0]["change_percent"]},
        "average_change_percent": round(sum(float(tile["change_percent"]) for tile in valid) / len(valid), 4),
        "sample_size": len(valid),
        "interpretation": "Relative movement only; not a personalized investment recommendation.",
    }
