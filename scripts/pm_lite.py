#!/usr/bin/env python3
"""pm_lite - Polymarket Complete-Set Checker (Lite). Read-only, educational.

Free cut-down of the Polymarket Edge Research Kit. It reads PUBLIC Polymarket
data and does arithmetic. It never places orders and never needs a wallet,
API key or private key. Nothing it prints is financial advice or a prediction.

Subcommands
  fee     taker fee for C shares at price p (Polymarket formula)
  calc    binary YES+NO complete-set math on two prices YOU type in (offline)
  check   live binary YES+NO check at the TOP of the order book only

Lite limits: binary markets only (no multi-outcome baskets), top-of-book only
(no depth walk), no market filter file, no CSV export, no EV/Kelly.

Python 3.9+, standard library only. License: MIT-0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

__version__ = "1.0.0"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = f"pm-lite/{__version__} (+research-only)"
FALLBACK_FEE_RATE = 0.07  # highest published category rate; used only when a market has no fee data

DISCLAIMER = ("Research output only. Top-of-book prices move and can be cancelled before you act. "
              "Not financial advice. Check that prediction markets are legal where you live.")


# ---------------- pure math ----------------

def taker_fee(shares: float, price: float, rate: float, exponent: float = 1.0) -> float:
    """Polymarket taker fee in USDC: C * rate * (p*(1-p))^exponent, 5 dp."""
    if shares <= 0 or rate <= 0:
        return 0.0
    p = min(max(price, 0.0), 1.0)
    return round(shares * rate * (p * (1.0 - p)) ** exponent, 5)


def binary_set_quote(yes: float, no: float, size: float, fee_rate: float,
                     mode: str = "buy", exponent: float = 1.0) -> dict:
    """YES+NO complete set. buy: pay yes+no+fees, merge for $1. sell: split $1, sell both minus fees."""
    for p in (yes, no):
        if not 0 < p < 1:
            raise ValueError("prices must be between 0 and 1")
    fees = taker_fee(size, yes, fee_rate, exponent) + taker_fee(size, no, fee_rate, exponent)
    gross = size * (yes + no)
    cost, proceeds = (gross + fees, size * 1.0) if mode == "buy" else (size * 1.0, gross - fees)
    profit = proceeds - cost
    return {
        "mode": mode, "size": size, "yes": yes, "no": no, "sum_prices": round(yes + no, 6),
        "gap_before_fees": round((1 - yes - no) if mode == "buy" else (yes + no - 1), 6),
        "fees": round(fees, 5), "cost": round(cost, 5), "proceeds": round(proceeds, 5),
        "profit_after_fees": round(profit, 5),
        "edge_pct": round(100 * profit / cost, 4) if cost else 0.0,
        "breakeven_sum_prices": round((1 - fees / size) if mode == "buy" else (1 + fees / size), 6) if size else None,
    }


def fee_rate_for(m: dict, override: Optional[float] = None) -> tuple:
    if override is not None:
        return override, "override"
    if m.get("feesEnabled") is False:
        return 0.0, "feesEnabled=false"
    s = m.get("feeSchedule")
    if isinstance(s, dict) and s.get("rate") is not None:
        try:
            return float(s["rate"]), f"feeSchedule:{m.get('feeType', '?')}"
        except (TypeError, ValueError):
            pass
    return FALLBACK_FEE_RATE, "fallback(no fee data)"


def _jsonlist(x) -> list:
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            v = json.loads(x)
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return []
    return []


def best(levels, side: str):
    """Best (price, size) on a raw CLOB side, or None."""
    lv = []
    for x in levels or []:
        try:
            p, s = float(x["price"]), float(x["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if s > 0 and 0 < p < 1:
            lv.append((p, s))
    if not lv:
        return None
    return min(lv) if side == "ask" else max(lv)


def check_market(m: dict, books: dict, fee_override: Optional[float] = None) -> list:
    """Top-of-book YES+NO check for one binary market. Returns 0-2 rows (buy / sell)."""
    toks = _jsonlist(m.get("clobTokenIds"))
    if len(toks) != 2 or toks[0] not in books or toks[1] not in books:
        return []
    rate, src = fee_rate_for(m, fee_override)
    ev = (m.get("events") or [{}])[0]
    url = f"https://polymarket.com/event/{ev.get('slug') or m.get('slug', '')}"
    rows = []
    for mode, side in (("buy", "ask"), ("sell", "bid")):
        y = best(books[toks[0]].get(side + "s"), side)
        n = best(books[toks[1]].get(side + "s"), side)
        if not y or not n:
            continue
        size = min(y[1], n[1])
        q = binary_set_quote(y[0], n[0], size, rate, mode)
        rows.append({
            "strategy": "buy YES+NO, merge" if mode == "buy" else "split $1, sell YES+NO",
            "title": m.get("question", ""), "yes": y[0], "no": n[0], "sum": q["sum_prices"],
            "gap_before_fees": q["gap_before_fees"], "top_size": round(size, 2),
            "fee_rate": rate, "fee_src": src, "profit_after_fees": q["profit_after_fees"],
            "edge_pct": q["edge_pct"], "url": url,
        })
    return rows


def market_ok(m: dict, min_liquidity: float) -> bool:
    if not m.get("active", True) or m.get("closed") or m.get("archived"):
        return False
    if m.get("enableOrderBook") is False or m.get("acceptingOrders") is False:
        return False
    if len(_jsonlist(m.get("clobTokenIds"))) != 2:
        return False
    try:
        liq = float(m.get("liquidityNum", m.get("liquidity")) or 0)
    except (TypeError, ValueError):
        liq = 0.0
    return liq >= min_liquidity


# ---------------- network (public, read-only) ----------------

def _req(url: str, body: Optional[bytes] = None, timeout: float = 15.0):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": UA, "Accept": "application/json",
                **({"Content-Type": "application/json"} if body else {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(0.15)
            return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            code = getattr(e, "code", None)
            if code and 400 <= code < 500 and code != 429:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed: {url} ({last})")


def fetch_markets(limit: int) -> list:
    out, offset = [], 0
    while len(out) < limit:
        n = min(100, limit - len(out))
        batch = _req(f"{GAMMA}/markets?active=true&closed=false&archived=false"
                     f"&order=volume24hr&ascending=false&limit={n}&offset={offset}")
        if not batch:
            break
        out.extend(batch)
        offset += len(batch)
        if len(batch) < n:
            break
    return out


def fetch_books(token_ids: list) -> dict:
    books = {}
    for i in range(0, len(token_ids), 50):
        res = _req(f"{CLOB}/books", json.dumps([{"token_id": t} for t in token_ids[i:i + 50]]).encode())
        for b in res or []:
            if isinstance(b, dict) and b.get("asset_id"):
                books[b["asset_id"]] = b
    return books


# ---------------- CLI ----------------

def print_table(rows: list, cols: list) -> None:
    if not rows:
        print("(no rows)")
        return

    def cell(v):
        s = "" if v is None else (f"{v:,.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
        return s if len(s) <= 55 else s[:54] + "…"
    w = {c: max(len(c), *(len(cell(r.get(c))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(w[c]) for c in cols))
    print("  ".join("-" * w[c] for c in cols))
    for r in rows:
        print("  ".join(cell(r.get(c)).ljust(w[c]) for c in cols))


def cmd_fee(a):
    f = taker_fee(a.shares, a.price, a.rate)
    print(json.dumps({"shares": a.shares, "price": a.price, "rate": a.rate, "fee_usdc": f,
                      "fee_per_share": round(f / a.shares, 6) if a.shares else 0}, indent=2))


def cmd_calc(a):
    print(json.dumps(binary_set_quote(a.yes, a.no, a.size, a.fee_rate, a.mode), indent=2))


def cmd_check(a):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ms = [m for m in fetch_markets(a.max_markets) if market_ok(m, a.min_liquidity)]
    toks = [t for m in ms for t in _jsonlist(m.get("clobTokenIds"))]
    print(f"# {ts}: {len(ms)} binary markets, fetching {len(toks)} books (top of book only)…", file=sys.stderr)
    books = fetch_books(toks)
    rows = [r for m in ms for r in check_market(m, books, a.fee_rate)]
    hits = [r for r in rows if r["profit_after_fees"] > 0]
    shown = rows if a.show_all else hits
    shown.sort(key=lambda r: (r["profit_after_fees"], r["gap_before_fees"]), reverse=True)
    shown = shown[: a.top]
    print(f"# {len(hits)} of {len(rows)} YES+NO checks show modelled profit after fees at the top of the book. "
          f"Zero is the normal result. {DISCLAIMER}", file=sys.stderr)
    if a.json:
        print(json.dumps(shown, indent=2))
    else:
        print_table(shown, ["strategy", "title", "yes", "no", "sum", "gap_before_fees", "top_size",
                            "fee_rate", "profit_after_fees", "url"])


def make_parser():
    p = argparse.ArgumentParser(prog="pm_lite", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("fee", help="taker fee for C shares at price p")
    s.add_argument("--shares", type=float, required=True)
    s.add_argument("--price", type=float, required=True)
    s.add_argument("--rate", type=float, required=True, help="e.g. 0.04")
    s.set_defaults(fn=cmd_fee)
    s = sp.add_parser("calc", help="YES+NO complete-set math on two prices you supply")
    s.add_argument("--yes", type=float, required=True)
    s.add_argument("--no", type=float, required=True)
    s.add_argument("--size", type=float, default=100.0, help="number of sets")
    s.add_argument("--fee-rate", type=float, default=0.0)
    s.add_argument("--mode", choices=["buy", "sell"], default="buy",
                   help="buy = asks, merge for $1; sell = split $1, sell at bids")
    s.set_defaults(fn=cmd_calc)
    s = sp.add_parser("check", help="live top-of-book YES+NO check on binary markets")
    s.add_argument("--max-markets", type=int, default=100, help="top markets by 24h volume (max 200 in lite)")
    s.add_argument("--min-liquidity", type=float, default=5000)
    s.add_argument("--fee-rate", type=float, help="override every market's fee rate")
    s.add_argument("--top", type=int, default=15)
    s.add_argument("--show-all", action="store_true", help="also show near misses with no edge")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_check)
    return p


def main(argv=None) -> int:
    a = make_parser().parse_args(argv)
    if getattr(a, "max_markets", 0) and a.max_markets > 200:
        a.max_markets = 200
    try:
        a.fn(a)
    except (RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
