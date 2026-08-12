#!/usr/bin/env python3
"""
generate_data.py — emits data.json for the Overround MM dashboard.

PHASE: the go/no-go re-sim COMPLETED 2026-08-07 with a QUALIFIED GREEN LIGHT, so this
dashboard now reports the decision + backtest result, plus live recorder status (which is
now accumulating a clean OUT-OF-SAMPLE window past the backtest cut-off).

Research constants below are transcribed from the study report and are marked as such:
    Documents/Zynerise/pitch/Overround_策略研究報告2.pdf  (2026-08-07)
Everything under "recorder" is read live from pm_micro.db.

PERFORMANCE: pm_micro.db is ~8.6 GB / ~103M rows on a small box, so every query here is
O(1) or O(log n) — MAX(rowid) for counts, rowid-ordered LIMIT 1 for the time window, and a
binary search over rowid for the out-of-sample split. No COUNT(*), no GROUP BY, no sort:
an earlier version full-scanned the table and never finished.

    python generate_data.py            # writes ./data.json
    python generate_data.py --stdout   # print (pipe over ssh)
"""

from __future__ import annotations
import argparse, json, sqlite3, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_BOX  = "aws-dublin"
SERVICE     = "pm-micro"
DEFAULT_DB  = Path.home() / "pm_crypto_trend" / "data" / "pm_micro.db"
OUT_PATH    = Path(__file__).with_name("data.json")

# ---- research constants (source: Overround_策略研究報告2.pdf, 2026-08-07) ----------------
DECISION_DATE = "2026-08-07"
BT_START, BT_END = "2026-07-22", "2026-08-06"      # backtest window (in-sample)
OOS_FROM_TS = datetime(2026, 8, 7, tzinfo=timezone.utc).timestamp()

CONFIGS = [  # spread, queue assumption, shares filled, net $, $/100sh
    {"spread": "1¢", "queue": "Q_SKIP", "shares":  70875, "net": 1707, "per100": 2.41},
    {"spread": "1¢", "queue": "Q_200",  "shares": 101171, "net": 2577, "per100": 2.55, "best": True},
    {"spread": "2¢", "queue": "Q_SKIP", "shares":  35493, "net":  529, "per100": 1.49},
    {"spread": "2¢", "queue": "Q_200",  "shares":  54801, "net": 1260, "per100": 2.30},
    {"spread": "4¢", "queue": "Q_SKIP", "shares":  13181, "net":  389, "per100": 2.96},
    {"spread": "4¢", "queue": "Q_200",  "shares":  30384, "net":  661, "per100": 2.17},
]

RISKS = [
    {"risk": "Queue position unverifiable", "impact": "high",
     "note": "87% of fills sat at levels where depth ahead couldn't be confirmed. Sign survives all 4 queue assumptions, but volume drops sharply under the conservative one."},
    {"risk": "Competitor reaction", "impact": "high",
     "note": "Backtest assumes the other ~27 pro makers don't react to our presence. In a live book they will."},
    {"risk": "Cancel/replace latency", "impact": "med",
     "note": "Live orders go through the REST API; quote-refresh speed is still unmeasured."},
    {"risk": "Sample period", "impact": "med",
     "note": "15 days, one market regime, no stress event. (The live recorder is now building an out-of-sample window against exactly this.)"},
    {"risk": "Daily hit rate", "impact": "med",
     "note": "79% is below the 85%+ typical of a mature making book; P&L also skews to the back of the sample."},
    {"risk": "Scale ceiling", "impact": "med",
     "note": "~$184/day at 25-share quotes. Scaling is capped by real order flow arriving at our price levels."},
    {"risk": "No rebate subsidy", "impact": "low",
     "note": "5-min markets sit outside the daily liquidity-rewards pool — the only maker income is 20% of the taker fee on filled size."},
]

NEXT_STEPS = [
    {"n": 1, "step": "Build the quoting engine", "detail": "order signing, live book stream, cancel/replace loop, kill switch", "eta": "1–2 weeks"},
    {"n": 2, "step": "Small live pilot", "detail": "one mid-liquidity market (ETH or SOL), minimum quote size", "eta": "2–4 weeks"},
    {"n": 3, "step": "Daily evaluation", "detail": "markout (fair-value drift 30s after fill) as the primary metric", "eta": "ongoing"},
    {"n": 4, "step": "Scale or kill", "detail": "positive markout + stable hit rate → scale gradually; otherwise shut it", "eta": "—"},
]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _service_active(name: str):
    try:
        r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"
    except Exception:
        return None


def _rowid_at(c, table: str, ts: float, lo: int, hi: int) -> int:
    """First rowid whose recv >= ts. Binary search — recv is monotonic (append-only)."""
    while lo < hi:
        mid = (lo + hi) // 2
        row = c.execute(f"select recv from {table} where rowid=?", (mid,)).fetchone()
        if row is None:                      # gap: probe forward
            lo = mid + 1
            continue
        if row[0] < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def build(db_path: Path) -> dict:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    tables = ("prints", "bba", "depth")
    totals, oos_totals = {}, {}
    win_lo = win_hi = None
    for t in tables:
        mx = c.execute(f"select max(rowid) from {t}").fetchone()[0] or 0
        totals[t] = mx
        f = c.execute(f"select recv from {t} order by rowid limit 1").fetchone()
        l = c.execute(f"select recv from {t} order by rowid desc limit 1").fetchone()
        if f and l:
            win_lo = f[0] if win_lo is None else min(win_lo, f[0])
            win_hi = l[0] if win_hi is None else max(win_hi, l[0])
            oos_totals[t] = max(0, mx - _rowid_at(c, t, OOS_FROM_TS, 1, mx)) if l[0] >= OOS_FROM_TS else 0
        else:
            oos_totals[t] = 0

    now = datetime.now(timezone.utc)
    oos_days = round((now.timestamp() - OOS_FROM_TS) / 86400, 1)

    return {
        "display_name":  "Overround MM",
        "status":        "decided",
        "phase":         "qualified green light · pilot pending",
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_box":    SOURCE_BOX,

        "decision": {
            "date": DECISION_DATE,
            "verdict": "Qualified green light",
            "headline": "+$2.55 per 100 shares",
            "call": "Small live pilot approved — NOT meaningful capital.",
            "report": "Overround_策略研究報告2.pdf",
        },

        "backtest": {
            "window": [BT_START, BT_END],
            "days": 15, "trading_days": 14, "windows": 15814,
            "rows": {"prints": 10_400_000, "bba": 63_000_000, "depth": 2_800_000},
            "configs": CONFIGS,
            "configs_positive": f"{sum(1 for x in CONFIGS if x['net'] > 0)} / {len(CONFIGS)}",
            "profitable_days": "11 / 14",
            "t_stat": 3.3, "p_value": 0.005,
            "worst_day": -144,
            "daily_avg": 184,
            "quote_size": "25 shares",
        },

        "key_finding": {
            "rejected": ("Model-anchored quoting FAILED: −$8–9 per 100sh. Two causes — our Chainlink feed "
                         "runs ~5s stale (at zero lag markout flips positive), and 33% of model quotes sat "
                         "ABOVE the market's best bid, i.e. arguing with the book."),
            "adopted": ("Book-mid anchored quoting: quote symmetrically around the order book's own mid. "
                        "No view, no model, no oracle — which also structurally removes the latency problem, "
                        "because the book is real-time."),
        },

        "recorder": {
            "service": SERVICE,
            "active": _service_active(SERVICE),
            "window_utc": [_iso(win_lo), _iso(win_hi)] if win_lo else None,
            "totals": totals,
            "oos": {"since": DECISION_DATE, "days": oos_days, "rows": oos_totals},
        },

        "risks": RISKS,
        "next_steps": NEXT_STEPS,
        "capital": {"pilot": "$500–1,000", "operating": "$10,000–20,000"},
        "notes": ("Backtest figures are transcribed from the 2026-08-07 study report; recorder figures are "
                  "read live. Still a promising hypothesis, not a validated business — no capital deployed."),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    if not Path(a.db).exists():
        print(f"[generate_data] DB not found at {a.db}; leaving data.json untouched", file=sys.stderr)
        sys.exit(0)
    payload = build(Path(a.db))
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if a.stdout:
        sys.stdout.write(text)
    else:
        OUT_PATH.write_text(text)
        r = payload["recorder"]
        print(f"wrote {OUT_PATH}  (totals={r['totals']}, oos_days={r['oos']['days']})")


if __name__ == "__main__":
    main()
