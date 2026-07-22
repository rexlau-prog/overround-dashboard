#!/usr/bin/env python3
"""
generate_data.py — emits data.json for the Overround MM dashboard.

The dashboard shell (index.html) fetches ./data.json every 60s and renders it.
Fill in the collect_* functions below with your strategy's real source (sim/book
state, fills log, Polymarket API, ...), flip STATUS to "sim" (or "paper"/"live"),
then:

    python generate_data.py                                  # writes ./data.json
    git commit -am "data $(date -u +%FT%TZ)" && git push     # publish

Run as-is and it reproduces the current "awaiting first data push" state with a
real timestamp. Field-by-field schema is documented in README.md.

The shared JSON keys carry market-making labels in this dashboard:
    sleeves        -> "Per-symbol"     (name = symbol, trades = rounds)
    open_positions -> "Live inventory" (side = net side, opened = since)
    recent_trades  -> "Recent fills"   (reason = type, return_pct = edge bps/%)
    recent_signals -> "Recent quotes"
Any numeric field left as None renders as "—", so partial fills are safe.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
STATUS     = "awaiting"          # "awaiting" -> amber banner. Flip to "sim"/"paper"/"live" once wired.
SOURCE_BOX = "aws-dublin"
CURRENCY   = "USD"
OUT_PATH   = Path(__file__).with_name("data.json")


# ---------------------------------------------------------------------------
# Data collectors — replace the bodies with your real source
# ---------------------------------------------------------------------------
def collect_kpis() -> dict:
    # TODO: pull from your sim/book state.
    return {
        "book_equity":    None,   # e.g. 10000
        "start_equity":   None,
        "realized_pnl":   None,   # signed; colours green/red
        "return_pct":     None,   # percent
        "open_positions": None,   # live inventory legs (int)
        "closed_trades":  None,   # completed rounds (int)
        "win_rate_pct":   None,   # 0..100
        "note":           None,   # e.g. "rebate 20% · fair-calibrated"
    }


def collect_equity_curve() -> dict:
    # TODO: (label, equity) points, oldest first.
    return {"labels": [], "values": []}


def collect_symbols() -> list[dict]:
    # Per-symbol P&L (rendered under "Per-symbol"). trades = rounds.
    return [
        # {"name": "BTC", "trades": 120, "win_pct": 54, "pnl": 62, "pf": 1.3},
        # {"name": "ETH", "trades": 98,  "win_pct": 51, "pnl": 18, "pf": 1.1},
    ]


def collect_inventory() -> list[dict]:
    # Live inventory (rendered under "Live inventory"). side = net side, opened = since.
    return [
        # {"market": "BTC 5m 14:05", "side": "+YES 3", "notional": "$45", "opened": "14:05:12"},
    ]


def collect_fills(limit: int = 15) -> list[dict]:
    # Recent fills (rendered under "Recent fills"). reason = type, return_pct = captured edge.
    return [
        # {"time": "14:03:58", "market": "ETH 5m 14:00", "side": "sell YES",
        #  "reason": "maker", "return_pct": 1.8, "pnl": 0.4},
    ]


def collect_quotes(limit: int = 15) -> list[dict]:
    # Recent quotes (rendered under "Recent quotes").
    return [
        # {"time": "14:04:10", "market": "BTC 5m 14:05", "side": "two-sided", "detail": "0.49 / 0.53  fair 0.51"},
    ]


# ---------------------------------------------------------------------------
def build_payload() -> dict:
    return {
        "display_name":   "Overround MM",
        "status":         STATUS,
        "generated_utc":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_box":     SOURCE_BOX,
        "currency":       CURRENCY,
        "kpis":           collect_kpis(),
        "equity_curve":   collect_equity_curve(),
        "sleeves":        collect_symbols(),
        "open_positions": collect_inventory(),
        "recent_trades":  collect_fills(),
        "recent_signals": collect_quotes(),
    }


def main() -> None:
    p = build_payload()
    OUT_PATH.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_PATH}  (status={p['status']}, generated={p['generated_utc']})")


if __name__ == "__main__":
    main()
