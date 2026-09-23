#!/usr/bin/env python3
"""Hourly price refresh for Luca's Stock Desk.

Reads tickers.json (page key -> Yahoo symbol), pulls six chart presets per
ticker from Yahoo Finance and writes data.json. Standard library only.
If a ticker fails, its previous data is kept instead of being blanked.
"""
import json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS = {"1m": ("1m", "1d"), "15m": ("15m", "5d"), "30m": ("30m", "1mo"),
           "1h": ("60m", "3mo"), "1M": ("1d", "1mo"), "6M": ("1d", "6mo")}
UA = "Mozilla/5.0"  # plain UA on purpose, full browser UAs get HTTP 429 from Yahoo
MAX_POINTS = 180


def fetch(symbol, interval, rng):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol) + f"?interval={interval}&range={rng}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)["chart"]["result"][0]
        except Exception as e:  # rate limit or network hiccup
            last = e
            time.sleep(2 + attempt * 3)
    raise last


def decimate(points):
    if len(points) <= MAX_POINTS:
        return points
    step = len(points) / MAX_POINTS
    return [points[int(i * step)] for i in range(MAX_POINTS - 1)] + [points[-1]]


def main():
    tickers = json.load(open(os.path.join(ROOT, "tickers.json")))
    out_path = os.path.join(ROOT, "data.json")
    old = {}
    if os.path.exists(out_path):
        try:
            old = json.load(open(out_path))
        except Exception:
            old = {}
    series, quotes = {}, {}
    for key, sym in tickers.items():
        try:
            s = {}
            for rkey, (interval, rng) in PRESETS.items():
                d = fetch(sym, interval, rng)
                ts = d.get("timestamp") or []
                cl = d["indicators"]["quote"][0].get("close") or []
                pts = [[t, round(c, 4)] for t, c in zip(ts, cl) if c is not None]
                m = d.get("meta", {})
                s[rkey] = {"points": decimate(pts), "currency": m.get("currency"),
                           "regularMarketPrice": m.get("regularMarketPrice")}
                if rkey == "1m":
                    quotes[key] = {"price": m.get("regularMarketPrice"),
                                   "prevClose": m.get("chartPreviousClose") or m.get("previousClose"),
                                   "currency": m.get("currency"),
                                   "time": m.get("regularMarketTime")}
                time.sleep(0.4)
            series[key] = s
            print("ok", key)
        except Exception as e:
            print("FAILED", key, e)
            if key in old.get("series", {}):
                series[key] = old["series"][key]
            if key in old.get("quotes", {}):
                quotes[key] = old["quotes"][key]
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quotes": quotes, "series": series}
    json.dump(data, open(out_path, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
