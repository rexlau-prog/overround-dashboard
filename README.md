# Overround MM · dashboard

Read-only dashboard for the **Overround** market-making strategy — two-sided quoting on Polymarket 5-minute
crypto Up/Down binaries, harvesting the book overround plus the 20% maker rebate. Simulated book (go/no-go
re-sim scheduled early Aug 2026). Live at **https://rexlau-prog.github.io/overround-dashboard/**.

The page (`index.html`) is a fixed shell that fetches **`data.json`** every 60 s and renders it. To update the
dashboard, the strategy box overwrites `data.json` and pushes — no HTML regeneration needed.

Part of the strategy hub: **https://rexlau-prog.github.io/**

## `data.json` contract

Same shape as the other hub dashboards, with market-making labels applied to the shared keys:

```jsonc
{
  "display_name": "Overround MM",
  "status": "sim",                   // "awaiting" | "sim" | "paper" | "live" | "archived"
  "generated_utc": "2026-07-22T14:00:00Z",   // null => amber "awaiting data" banner
  "source_box": "aws-dublin",
  "currency": "USD",

  "kpis": {
    "book_equity": 10000, "start_equity": 10000,
    "realized_pnl": 0, "return_pct": 0.0,
    "open_positions": 0,             // shown as "Open positions" = live inventory legs
    "closed_trades": 0,              // = completed rounds
    "win_rate_pct": 0,
    "note": ""
  },

  "equity_curve": { "labels": ["07-22 04:00"], "values": [10000] },

  "sleeves":        [ /* per-SYMBOL: { name:"BTC", trades:rounds, win_pct, pnl, pf } */ ],
  "open_positions": [ /* live INVENTORY: { market, side:net side, notional, opened:since } */ ],
  "recent_trades":  [ /* recent FILLS: { time, market, side, reason:type, return_pct:edge, pnl } */ ],
  "recent_signals": [ /* recent QUOTES: { time, market, side, detail } */ ]
}
```

The `index.html` renders `sleeves` under **Per-symbol**, `open_positions` under **Live inventory**,
`recent_trades` under **Recent fills**, and `recent_signals` under **Recent quotes**. Any numeric field set to
`null` (or omitted) renders as `—`, so partial pushes are safe.
