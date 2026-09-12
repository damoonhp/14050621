# CodexBot

[فارسی](README.md)

CodexBot is a local, safety-first PySide6 workstation for Bitunix USDT-M perpetual futures. It supports multiple strategy profiles, realistic backtesting, real-market-data paper trading, and deliberately gated live execution. It does **not** promise profitability.

> [!WARNING]
> This is experimental trading software, not financial advice. Start in `PAPER` mode, review the source, and validate every strategy yourself. Live trading can lose real money.

## Features

- Desktop dashboard, candlestick chart, strategy settings, logs, and CSV trade export.
- Public Bitunix market data without an API key.
- Deterministic multi-timeframe backtesting with fees, slippage, leverage, and no-lookahead alignment.
- Local paper execution that cannot call the live order endpoint.
- Gated Bitunix live execution with account preflight checks, exchange-native protection, and explicit confirmations.
- Six research/diagnostic strategy profiles, including SP2L and bounded grid execution.
- Automated tests for strategy, risk, exchange, backtest, GUI, and persistence behavior.

## Strategies

The strategy selector is shared by backtesting, paper trading, and live evaluation. Each
profile applies its required timeframes and research defaults automatically:

- **TestStrategy** — a diagnostic-only 1m/5m profile that deterministically emits
  the selected LONG or SHORT direction and is limited to one protected market-order
  request per bot run. Selecting it in Live adds an explicit immediate-order warning.
  It is not an alpha strategy and has no profitability claim.
- **GridStrategy** — an experimental bounded 15m/4h trend-pullback grid. It requires
  a completed-4H EMA50/EMA200 regime and slope, 1–3% EMA separation, acceptable ATR,
  above-median volume, and an RSI transition into a pullback. Two equal-weight limits
  sit one ATR apart; martingale sizing is not used. One hard stop protects the whole
  grid, targets preserve at least 2R from the shallowest possible fill, unfilled orders
  expire after six bars, and filled plans time out after twenty-four bars.
- **EMA Trend Pullback** — the original 15m/1h long-short baseline.
- **SP2L (Poursamadi Spike-2Leg)** — a causal 1m/5m price-action implementation
  that identifies a 3–9 candle breakout spike, requires a pressure gap, rejects
  dirty pre-spike price action, and arms scaled resting limits only after the first
  pullback candle closes. The default is the publicly documented two-layer entry;
  the aggressive third 4x layer is disabled unless explicitly enabled.
- **Vibe 4H / Daily Breakout** — the migrated long-only 4H breakout gated by a completed
  daily EMA50/RSI regime. A CodexBot replay over the available 2025-01-01 through
  2026-08-27 VibeCode data returned +4.84%, profit factor 1.48, and 3.30% maximum
  drawdown at 0.5% risk, with modeled fees and slippage. This remains a small 33-trade
  research sample, not proof of a future edge.
- **Vibe 4H Candle Confirmation (Market)** — a 15m/4h market-entry adaptation of the
  VibeCode maker strategy. The old maker-fill performance must not be attributed to this
  version: the CodexBot market replay was negative, so this profile is experimental and
  requires new validation before any live consideration.

The application rejects a strategy/timeframe mismatch instead of silently running a
profile on data it was not designed for.

### GridStrategy validation record

The promoted default was selected from a small bounded search over layer count, ATR
spacing, stop buffer, and time stop using BTCUSDT data from 2026-05-01 through
2026-06-30. Fees were 0.06% per fill, slippage 0.03%, risk 0.5%, leverage 2x, and the
2R requirement remained fixed. BTC training returned +4.84% (PF 7.17, five partial
exit records); the untouched 2026-07-01 through 2026-08-30 holdout contained only one
losing plan and returned -1.43%. The combined BTC window returned +3.34%, PF 2.46,
and 1.52% maximum drawdown. The same defaults on ETHUSDT returned +3.83%, PF 2.51,
and 3.45% maximum drawdown over the combined window; its earlier segment was -1.44%
and its later holdout was +5.34%. These samples are small and mixed. They justify an
experimental backtest/paper profile, not a promise of live profitability.

### SP2L execution rules

- Bullish spikes require consecutive non-decreasing lows; bearish spikes require
  consecutive non-increasing highs. A spike longer than nine candles is rejected as
  potential exhaustion.
- The first or second spike candle must make a strong close through the prior static
  range, and the follow-through bar must leave a pressure gap relative to the
  pre-breakout candle.
- The optimized BTCUSDT profile scans the full weekday session and aligns shorts
  with the last completed 15m EMA60 regime. The London/New York-only session filter
  and both-direction mode remain available for other instruments and research.
- The first strict low/high violation is the pullback trigger. Because the bot uses
  closed candles, the trigger arms resting limits for later candles and never claims
  an unknowable fill inside the trigger candle.
- Entry 1 retests the prior candle low/high. The optimized BTCUSDT profile places
  Entry 2 at EMA60; midpoint-to-stop and spike-midpoint modes remain configurable.
  Entry 3 uses the requested 4x weight near the stop but is opt-in.
- Stops can use spike origin (default), follow-through candle, or the 50% spike level.
  The optimized profile takes 70% at 1R; TP2 uses the farther of the measured move
  and the machine-required 2R minimum. Unfilled limits expire after five bars and
  open trades time out after thirty bars.
- The backtester models every layer, partial TP1, TP2, stop, limit expiry, fees,
  leverage, and time stop. Paper mode creates real local resting limits and splits
  each layer into TP1/TP2 quantities. Live mode submits the same slices as tracked
  GTC limit orders with unique client IDs and exchange-native market SL/TP triggers.

The source method describes gold, indices, and forex, but this repository's exchange
adapter currently supports Bitunix USDT perpetual symbols only. XAUUSD and US30 need a
separate broker/data adapter; the strategy logic itself is asset-agnostic.

Public method references: [Mohammad Ali Poursamadi's SP2L overview](https://poursamadi.com/en/sp2l-strategy-spike-2leg-by-mohammad-ali-poursamadi/)
and the [TradingFinder SP2L indicator description](https://www.tradingview.com/script/Qiv9aTi0-SP2L-Pour-Samadi-Indicator-TradingFinder-Spike-2-Legs-PA/).

### SP2L optimization record

The BTCUSDT 5m defaults were selected from a deterministic 1,024-trial broad search
followed by a 768-trial neighborhood search over 2026-05-30 through 2026-08-30.
Development used three chronological folds ending 2026-08-01; 2026-08-01 through
2026-08-30 was held out until finalist validation. Risk stayed at 0.5%, fees at
0.06% per fill, adverse slippage at 0.03%, and the gap/2R safety requirements were
never optimized away. The promoted profile produced +4.02%, profit factor 3.00,
0.88% maximum drawdown, and 35 recorded exits over the full sample; the untouched
holdout produced +0.46%, profit factor 1.79, and 13 exits. These are small historical
samples, not a profitability guarantee. Revalidate on newer data before live use.
Execution-cost stress remained positive at 0.08% fee plus 0.05% slippage (+2.54%,
PF 1.98) and at 0.10% fee plus 0.07% slippage (+1.08%, PF 1.33), but failed at
0.15% fee plus 0.10% slippage (-2.02%). This profile is therefore cost-sensitive.

The reproducible optimizer is `scripts/optimize_sp2l.py`; detailed broad and focused
results are stored under `optimization/`.

### VibeCode parity check

The Vibe 4H / Daily Breakout was replayed in both engines over the same Bitunix files
and 2025-01-01 through 2026-08-27 window with $10,000 starting equity, 0.5% risk,
1x leverage, 0.06% fee per fill, 0.03% slippage, ATR 2.0, R:R 2:1, and weekend
filtering disabled. The results match to floating-point precision:

| Engine | Return | Profit factor | Trades | Max drawdown |
|---|---:|---:|---:|---:|
| VibeCode | 4.8224256522% | 1.4827427242 | 33 | 3.1850462636% |
| CodexBot | 4.8224256522% | 1.4827427242 | 33 | 3.1850462636% |

CodexBot keeps weekend blocking enabled by default to follow the machine trading policy.
With that policy enabled on the same sample, CodexBot produced 30 trades, +4.96%,
profit factor 1.56, and 2.86% maximum drawdown. This is a policy-adjusted result, not the
strict VibeCode parity run.

The Backtest tab exposes leverage and weekend filtering. Selecting a strategy loads its
research risk, leverage, fee, slippage, ATR, R:R, and timeframe preset; weekend blocking
remains an explicit visible choice.

## Safety model

- The default mode is `PAPER`.
- Paper orders are executed only by `PaperExchange`; they never call Bitunix's order endpoint.
- Risk per trade is capped at 1% and configured reward/risk cannot be below 2:1, matching the machine trading policy.
- Weekend entries are blocked by default. Turn on **Macro Event Blackout** before CPI/FOMC windows; the application does not guess an economic calendar.
- Live mode requires credentials in environment variables, a successful authenticated connection test, selection of `LIVE`, a warning dialog, and the confirmation `yes`.
- SP2L live execution preserves its scaled GTC limits and separate TP1/TP2 quantities;
  a partial submission is rolled back instead of degrading the plan into a market order.
- GridStrategy uses the same tracked, rollback-safe GTC limit engine with `cbgrid` client
  IDs. Total plan quantity is risk-sized once, split equally, and rounded down so layer
  precision cannot increase the requested exposure.
- Live execution supports Bitunix `ONE_WAY` position mode. If the account is in `HEDGE` mode, the application checks all futures symbols first, offers to cancel only stale CodexBot-owned orders with a typed `yes`, requires external orders and positions to be cleared by the user, changes the account-wide mode after a second typed `yes`, and verifies the result.
- Starting Live reads the selected symbol's current leverage and margin mode. It changes only mismatched values after explicit confirmation and verifies both through Bitunix's read endpoint.
- Stopping Live asks for typed confirmation when CodexBot entry orders remain, cancels only those orders, and polls until Bitunix confirms they are no longer pending. Existing exchange positions are never silently closed.
- Live account balances, unrealized PnL, positions, and pending orders are cached from authenticated Bitunix REST responses; the Dashboard never substitutes paper-wallet values in Live mode.
- Public market-data and private order/position WebSocket health are tracked and displayed separately.
- Credentials are loaded only from `BITUNIX_API_KEY` and `BITUNIX_API_SECRET`. They are never persisted or shown in logs.
- No withdrawal feature exists.

Use an API key with only the permissions required for futures trading. Withdrawal permission is neither needed nor recommended.

## Install and launch

### Requirements

- Windows 10/11 (the documented commands use PowerShell)
- Python 3.11 or newer; Python 3.13.2 was used during development
- Internet access for Bitunix public market data

### From a ZIP download

Extract the archive, open PowerShell in the extracted `CodexBot` folder, and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "."
python main.py
```

Creating `.env` is unnecessary for backtesting and paper trading. To install the test tools as well, replace the install command with:

```powershell
python -m pip install -e ".[dev]"
```

On later launches:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

If PowerShell blocks virtual-environment activation, use the interpreter directly:

```powershell
.\.venv\Scripts\python.exe main.py
```

### From GitHub

On the GitHub repository page, select **Code**, copy the HTTPS URL, then clone it and follow the same setup commands:

```powershell
git clone https://github.com/erfanrhb/CodexBot.git
Set-Location CodexBot
```

Public market data, paper trading, and backtests do not need credentials. For authenticated connection testing and live mode, set the variables in `.env` locally:

```dotenv
BITUNIX_API_KEY=
BITUNIX_API_SECRET=
```

Never commit `.env`; it is ignored by Git.

Settings saved in the GUI go to the local `config.json`. Downloaded candles go to `cache/`, trade exports go to `exports/`, and logs may be written as `*.log`. These runtime files are intentionally excluded from Git and release archives. Deleting them resets local settings/history but does not remove source code.

Bitunix does not provide a demo environment used by this application. `PAPER` mode
therefore consumes real public Bitunix prices but executes every order inside the local
`PaperExchange`; it never calls an authenticated Bitunix order endpoint.

## GUI workflow

### Backtest

1. Open **Backtest**.
2. Choose symbol, strategy, date range, starting balance, higher/entry timeframes, fee, slippage, risk, risk/reward, and ATR multiplier.
3. Select **RUN BACKTEST**. Data retrieval and calculation run on a Qt worker thread, so the window remains responsive.
4. Review statistics, equity curve, and trade history. Use **EXPORT TRADES CSV** to save the trades.
5. **CANCEL** requests deterministic cancellation between processing steps.

Historical Bitunix data is cached under `cache/`. Only completed candles are admitted. Data is sorted and checked for duplicate timestamps, malformed OHLC values, and timeframe consistency. The official feed has occasionally returned a `high`/`low` one tick inside its own open/close envelope; the Bitunix adapter clamps only that envelope before strict validation.

### Paper trading

1. Open **Paper / Live** and leave the mode as `PAPER`.
2. Select **START BOT**.
3. The engine receives current ticker/candle updates over the public Bitunix WebSocket, loads only closed candles for signals, performs precision-aware risk validation, and creates local simulated orders. Bounded REST polling is the recovery path when the stream is stale.
4. Fees, adverse slippage, leverage-based margin reservation, affordability-capped position size, SL, and TP are modeled.
5. Select **STOP BOT** to prevent new signals. Existing paper positions remain represented locally.

### Live trading

1. Configure the strategy, risk, leverage, margin mode, and symbol first.
2. Put credentials in the local environment and use **Exchange → TEST CONNECTION**.
3. Select `LIVE`, then **START BOT**.
4. Read the warning and type `yes`.
5. Live preflight rejects existing positions and external pending orders. If it finds stale `cb*` orders from an earlier CodexBot session, type `yes` to cancel and verify only those orders.
6. If the account is in `HEDGE` mode, read the account-wide warning and type `yes` to let CodexBot request and verify `ONE_WAY` mode.
7. If leverage or margin mode differs, review the before/after values and type `yes` to change and verify only the selected symbol.
8. The engine rechecks positions, pending orders, `ONE_WAY`, leverage, margin mode, and instrument precision before enabling execution. SP2L orders remain resting until filled or expired and retain their exchange-native SL/TP protection.
9. When stopping Live, type `yes` if prompted to cancel and verify CodexBot-owned pending entries. Existing positions stay open with their exchange protection.

Live order submission is implemented, including market direction, base-coin quantity, `reduceOnly`, and exchange-native LAST_PRICE market SL/TP fields. It has **not** been executed against a funded account during development. Do not use live mode until you have reviewed the code and validated it with your own restricted API key and account configuration.

### Real API test order

The **Exchange** tab includes **TEST ORDER** for checking the complete authenticated order route without starting the bot. Enter the exact futures symbol, direction, order size in USDT notional, limit entry, stop loss, take profit, and leverage. CodexBot converts the USDT size to Bitunix's required base-coin quantity at the entered limit price and rounds it down to exchange precision. The app requires an idle bot, authenticated credentials, no conflicting positions/orders, `ONE_WAY` position mode, valid Bitunix precision, at least 2:1 reward/risk, and estimated stop risk no greater than 1% of account equity.

After the user reviews the real-funds summary and types `yes`, CodexBot applies and verifies a leverage change only when needed, submits one protected real limit order, reads its authoritative Bitunix status, and immediately cancels and verifies any unfilled remainder. Bitunix has no demo endpoint for this workflow. A marketable limit can fill before cancellation; the result panel reports the order ID and filled quantity, and CodexBot never silently closes a resulting real position.

The public and private WebSocket clients send Bitunix application heartbeats on a fixed deadline even during continuous market traffic. Unexpected transport loss still triggers bounded automatic reconnection; a later `CONNECTED` status confirms recovery.

## Backtest execution rules

- Candle timestamps represent candle opens. Candle close time is derived from the timeframe.
- A signal calculated at candle N close executes at candle N+1 open, with adverse configurable slippage.
- Higher-timeframe values become visible only when their higher-timeframe candle has completed. Alignment uses backward as-of matching against derived close times.
- Position quantity risks the configured account percentage from entry to ATR stop, is capped by leverage-based available margin plus entry fee, and is rounded down to the exchange's base precision.
- Prices are rounded to exchange quote precision. Minimum quantity and maximum market quantity come from Bitunix instrument metadata; minimum notional is checked when the exchange supplies one.
- Entry and exit fees are charged independently.
- If SL and TP are both inside one OHLC candle and tick order is unavailable, SL wins. This is deterministic and conservative for both long and short trades.
- An open position at the end of data closes at the final close with adverse slippage and fees.

## Architecture

```text
PySide6 GUI
  -> ApplicationController / services
    -> TradingService or BacktestService
      -> selected strategy from registry + RiskManager
        -> PaperExchange or BitunixClient
```

The GUI contains no exchange signing, strategy, sizing, or backtest calculations. The trading service works without the GUI. Explicit `STOPPED`, `CONNECTING`, `RUNNING_BACKTEST`, `RUNNING_PAPER`, `RUNNING_LIVE`, and `ERROR` states prevent conflicting operations and repeated starts.

```text
app/             application controller
backtesting/     sequential simulator and metrics
config/          validated settings and persistence
data/            historical download, cache, validation
engine/          application state machine
execution/       exchange abstraction, Bitunix REST/WS, paper exchange
gui/             PySide6 views, chart, worker
indicators/      EMA, RSI, ATR
models/          orders, signals, positions, trades, results
risk/            position sizing, stops, targets, precision
services/        backtest and independent trading services
strategies/      registry, EMA baseline, 4H/daily breakout, and 4H confirmation
tests/           deterministic automated tests
utils/           logging integration
scripts/         safe integration smoke checks
main.py          desktop entry point
```

## Tests and verification

Run the deterministic suite:

```powershell
python -m pytest
```

Run the safe public WebSocket and complete offscreen GUI/backtest acceptance checks:

```powershell
python scripts/ws_smoke.py
python scripts/gui_acceptance.py
```

The suite covers configuration validation/persistence, EMA/RSI/ATR, trend and long/short signals, multi-timeframe alignment/no-lookahead, sizing and limits, stops/targets, fees/slippage, long and short backtests, same-candle conflict policy, official signing construction, response/order parsing, paper execution/position management, historical validation, and application-state conflicts.

Verified during development:

- 76 automated tests pass;
- the GUI constructs and exits successfully in an offscreen Qt smoke test;
- a GUI-triggered worker backtest downloaded public Bitunix history and populated all 13 metric cards and 34 trade-table rows;
- public instrument metadata, ticker, and historical kline REST calls work;
- a real public BTCUSDT 14-day integration backtest completed over more than 1,300 entry candles; weekend entries were excluded by policy;
- public Bitunix WebSocket ticker subscription receives data;
- authenticated Bitunix account, position, pending-order, leverage, and margin-mode reads work;
- private Bitunix WebSocket login and order/position subscription complete successfully with the configured restricted credentials;
- paper mode consumed current WebSocket market data and, because verification ran on a Sunday, correctly rejected the signal under the weekend-liquidity rule; deterministic tests verify local `paper-*` execution without reaching the live adapter.

Not safely verified:

- live order placement, fill reconciliation, cancellation, or funded-account behavior.
- no private order/position event was generated during the read-only handshake test.

## Bitunix API contract

The implementation follows the current official futures documentation:

- [Futures introduction and domains](https://www.bitunix.com/api-docs/futures/common/introduction.html)
- [Double-SHA256 REST/WebSocket signing](https://www.bitunix.com/api-docs/futures/common/sign.html)
- [Trading-pair precision and limits](https://www.bitunix.com/api-docs/futures/market/get_trading_pairs.html)
- [Historical klines](https://www.bitunix.com/api-docs/futures/market/get_kline.html)
- [Place order](https://www.bitunix.com/api-docs/futures/trade/place_order.html)
- [WebSocket endpoints, heartbeat, and limits](https://www.bitunix.com/api-docs/futures/websocket/prepare/WebSocket.html)

The private WebSocket documentation describes seconds while one example shows milliseconds; Bitunix accepted the documented seconds-based signature during a live read-only handshake. The client also consumes Bitunix's initial `connect` greeting before validating the subsequent `login` result. The order documentation's hedge-mode close-side prose is avoided by the `ONE_WAY` model using `reduceOnly` for reductions.

## Troubleshooting

- **`python` is not recognized:** install Python 3.11+ from python.org and enable the installer option that adds Python to `PATH`.
- **Qt platform/plugin error:** activate the project virtual environment and reinstall with `python -m pip install --force-reinstall PySide6`.
- **No market data:** check the internet connection and whether Bitunix is reachable from your network. Cached candles are not bundled with releases.
- **Live authentication fails:** verify the two `.env` names exactly, restart the app after changing them, and confirm the API key has the required futures permissions. Withdrawal permission is not required.
- **A strategy rejects the selected timeframes:** reselect the strategy to apply its fixed timeframe preset.

## Privacy and security

Release archives and Git commits must not contain `.env`, `config.json`, caches, exports, logs, coverage output, IDE settings, or Python build artifacts. The included `.env.example` contains blank placeholders only. If credentials were ever committed, deleting the file is not sufficient—rotate the keys and purge them from Git history before publishing.

## License

CodexBot is released under the [MIT License](LICENSE).
