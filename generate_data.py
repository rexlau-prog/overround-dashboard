#!/usr/bin/env python3
"""
generate_data.py — emits data.json for the Overround MM dashboard.

Overround is PRE-LAUNCH: a read-only recorder (`pm-micro`) is collecting Polymarket
5-min crypto microstructure (prints + best-bid/ask + L2 depth) into pm_micro.db, and a
fair-value calibration is fit into calibration.json. NO trading happens yet — the go/no-go
income-side re-sim is scheduled for the decision date. So this dashboard is a DATA-BUILD
STATUS view (recorder coverage + calibration), not a trade/P&L view.

Run on the box that owns pm_micro.db, or pass paths:

    python generate_data.py                       # writes ./data.json
    python generate_data.py --stdout              # print JSON (for piping over ssh)
    python generate_data.py --db /path/pm_micro.db --calib /path/calibration.json

If the DB isn't found it leaves data.json untouched. Schema documented in README.md.
"""

from __future__ import annotations
import argparse, json, sqlite3, subprocess, sys, os
from datetime import datetime, timezone
from pathlib import Path

SOURCE_BOX    = "aws-dublin"
SERVICE       = "pm-micro"
DECISION_DATE = "2026-08-05"          # go/no-go income-side re-sim (box cron: 0 1 5 8 *)
MARKET_ORDER  = ["btc", "eth", "sol", "xrp"]
DEFAULT_DB    = Path.home() / "pm_crypto_trend" / "data" / "pm_micro.db"
DEFAULT_CALIB = Path.home() / "pm_crypto_trend" / "data" / "calibration.json"
OUT_PATH      = Path(__file__).with_name("data.json")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _service_active(name: str):
    try:
        r = subprocess.run(["systemctl", "is-active", name],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"
    except Exception:
        return None


def build(db_path: Path, calib_path: Path) -> dict:
    c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row

    tables = ["prints", "bba", "depth"]
    per_market: dict[str, dict] = {}
    totals: dict[str, int] = {}
    win_lo = win_hi = None
    for t in tables:
        totals[t] = c.execute(f"select count(*) from {t}").fetchone()[0]
        row = c.execute(f"select min(recv), max(recv) from {t}").fetchone()
        if row and row[0] is not None:
            win_lo = row[0] if win_lo is None else min(win_lo, row[0])
            win_hi = row[1] if win_hi is None else max(win_hi, row[1])
        for sym, n in c.execute(f"select symbol, count(*) from {t} group by symbol"):
            per_market.setdefault(sym, {})[t] = n

    def market_rows():
        seen = list(MARKET_ORDER) + [s for s in per_market if s not in MARKET_ORDER]
        out = []
        for s in seen:
            if s not in per_market:
                continue
            m = per_market[s]
            out.append({"market": s.upper(),
                        "prints": m.get("prints", 0),
                        "bba":    m.get("bba", 0),
                        "depth":  m.get("depth", 0)})
        return out

    window_hours = round((win_hi - win_lo) / 3600, 1) if (win_lo is not None and win_hi is not None) else None

    # --- calibration ---
    calib = {"fit": False, "bands": [], "samples_total": 0}
    if calib_path.exists():
        try:
            raw = json.loads(calib_path.read_text())
        except (ValueError, OSError):
            raw = None
        if isinstance(raw, dict):
            bands = []
            samples = 0
            # present far-from-expiry -> near-expiry
            for key in ("early", "mid", "late"):
                b = raw.get(key)
                if not isinstance(b, dict):
                    continue
                ntr, nte = b.get("n_train", 0), b.get("n_test", 0)
                samples += ntr + nte
                lo, hi = b.get("tau_lo"), b.get("tau_hi")
                tau = f"{lo}–{hi}s" if (lo is not None and hi is not None) else None
                bands.append({"band": key, "tau": tau,
                              "a": b.get("a"), "b": b.get("b"),
                              "n_train": ntr, "n_test": nte})
            calib = {"fit": bool(bands), "bands": bands, "samples_total": samples,
                     "fit_utc": _iso(calib_path.stat().st_mtime)}

    return {
        "display_name":  "Overround MM",
        "status":        "recording",
        "phase":         "pre-launch · data build",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_box":    SOURCE_BOX,
        "decision_date": DECISION_DATE,
        "recorder": {
            "service":  SERVICE,
            "active":   _service_active(SERVICE),
            "recording_since_utc": _iso(win_lo) if win_lo is not None else None,
            "window_utc": [_iso(win_lo), _iso(win_hi)] if win_lo is not None else None,
            "window_hours": window_hours,
            "totals": {"prints": totals.get("prints", 0),
                       "bba": totals.get("bba", 0),
                       "depth": totals.get("depth", 0)},
        },
        "markets": market_rows(),
        "calibration": calib,
        "notes": ("Read-only recorder — NO trading. At the decision date the income-side "
                  "re-sim runs (calibrated fair + benign/toxic print split + queue/depth fill "
                  "model) to decide go/no-go on a tiny live maker pilot."),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--calib", default=str(DEFAULT_CALIB))
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    if not Path(a.db).exists():
        print(f"[generate_data] DB not found at {a.db}; leaving data.json untouched", file=sys.stderr)
        sys.exit(0)
    payload = build(Path(a.db), Path(a.calib))
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if a.stdout:
        sys.stdout.write(text)
    else:
        OUT_PATH.write_text(text)
        r = payload["recorder"]["totals"]
        print(f"wrote {OUT_PATH}  (prints={r['prints']}, bba={r['bba']}, depth={r['depth']}, "
              f"calib_bands={len(payload['calibration']['bands'])})")


if __name__ == "__main__":
    main()
