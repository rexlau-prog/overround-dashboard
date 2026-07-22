# Overround MM · dashboard

Read-only dashboard for the **Overround** market-making strategy — two-sided quoting on Polymarket 5-minute
crypto Up/Down binaries, harvesting the book overround plus the 20% maker rebate. Live at
**https://rexlau-prog.github.io/overround-dashboard/**.

**Status: pre-launch (data build).** No trading happens yet. A read-only recorder (`pm-micro`) collects
Polymarket 5-min microstructure into `pm_micro.db`, and a fair-value calibration is fit into
`calibration.json`. The go/no-go income-side re-sim is scheduled for the decision date (2026-08-05). So this
page is a **data-collection status view** (recorder coverage + calibration), not a trade/P&L view — it will be
swapped to a trade layout if/when the strategy goes live.

The page (`index.html`) fetches **`data.json`** every 60 s and renders it. `generate_data.py` reads
`pm_micro.db` + `calibration.json` on the box and emits `data.json`:

    python generate_data.py --stdout   # print (pipe over ssh)
    ssh dublin 'python3 - --stdout' < generate_data.py > data.json && git commit -am data && git push

Part of the strategy hub: **https://rexlau-prog.github.io/**

## `data.json` contract (pre-launch status)

```jsonc
{
  "display_name": "Overround MM",
  "status": "recording",            // "awaiting" | "recording"  (trade layout comes later)
  "phase": "pre-launch · data build",
  "generated_utc": "2026-07-22T07:38:46Z",
  "source_box": "aws-dublin",
  "decision_date": "2026-08-05",     // page computes the "Decision in N days" countdown client-side

  "recorder": {
    "service": "pm-micro",
    "active": true,                  // systemctl is-active (true | false | null)
    "recording_since_utc": "2026-07-22T05:44Z",
    "window_utc": ["2026-07-22T05:44Z", "2026-07-22T07:38Z"],   // current DB min/max recv
    "window_hours": 1.9,
    "totals": { "prints": 66056, "bba": 334861, "depth": 15940 }
  },

  "markets": [                       // per-market row counts (prints / best-bid-ask / L2 depth)
    { "market": "BTC", "prints": 52297, "bba": 144330, "depth": 6796 }
  ],

  "calibration": {
    "fit": true,
    "fit_utc": "2026-07-22T05:46Z",
    "samples_total": 101212,
    "bands": [                       // P = Φ(a·z + b) per time-to-expiry band; a<1 = shrink toward 0.5
      { "band": "early", "tau": "180–300s", "a": 0.65, "b": 0.0, "n_train": 27000, "n_test": 6750 }
    ]
  },

  "notes": "Read-only recorder — NO trading. ..."
}
```

Set `status: "awaiting"` (or leave `generated_utc` null) to show the amber "awaiting data" banner instead of
the status view. When the strategy goes live post-decision, this contract is replaced by the standard trade
schema (KPIs / equity_curve / sleeves / positions / trades) used by the other hub dashboards.
