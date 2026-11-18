# Orochi Terminal — Alpaca Paper Trading

A Python paper-trading project with multi-timeframe market data, an Orochi-inspired regime filter, ICT-style fair value gaps, basic news sentiment, risk-based sizing, and a Streamlit dashboard.

> **Paper trading only.** The trading client is explicitly initialized with `paper=True`. Do not put live credentials in `.env`. This is an educational strategy prototype, not a validated profitable system.

## Requirements

Use **Python 3.11–3.13** for the most predictable compatibility with Alpaca and the scientific Python packages. Python 3.15 may not yet be supported by every dependency.

### Windows PowerShell

```powershell
cd path\to\paper-trading-bot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and add your **Alpaca paper** API key and secret. Keep `.env` private; it is excluded by `.gitignore`.

```env
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here
```

## Run

```powershell
# Dashboard
streamlit run dashboard/app.py

# Scan and print analysis
python run_scan.py

# Scan and submit paper orders
python run_scan.py --execute

# Scheduled daily paper scan (Eastern Time)
python auto_trader.py

# Run once immediately
python auto_trader.py --once
```

## Safety and execution behavior

- Alpaca `TradingClient` is hard-coded to paper mode.
- The daily loss check fails closed: if the account/risk check cannot be verified, execution is blocked.
- New entries are long-only. A bearish signal can close an existing long; it does not open a short position.
- Existing positions are not pyramided. The bot respects the configured maximum number of positions and blocks entries once gross exposure reaches 75% of equity.
- Position sizing uses the configured risk percentage, an ATR stop-distance estimate, and the per-symbol allocation cap. This project submits market orders; it does **not** submit broker-side stop-loss orders. The sizing stop is therefore a risk estimate, not a guaranteed exit.
- Stocks are submitted as whole shares; crypto quantities are rounded to six decimals. A quantity that rounds to zero is rejected rather than submitted.
- The automatic scheduler runs once per weekday between 9:45 AM and 3:00 PM Eastern Time. `--once` runs immediately; `--force` bypasses the schedule.

## Strategy overview

| Component | Current behavior |
|---|---|
| Regime | Rolling VWAP distance, ATR, and EMA structure |
| FVG | Three-candle gap detection on 15-minute bars; mitigated gaps are excluded |
| Bias | 1-hour regime bias |
| Entry signal | Requires threshold confluence, directional HTF bias, and an aligned active FVG |
| News | TextBlob polarity when installed; conservative phrase matching fallback otherwise |
| Sizing | ATR-based risk estimate capped by `MAX_POSITION_PCT` |
| Markets | QQQ, SPY, selected mega-cap stocks, and Alpaca crypto pairs |

The 5-minute timeframe is calculated for display/analysis context but is not currently an independent entry trigger. The regime/FVG logic is a simplified approximation, not a full implementation of auction market theory or ICT.

## Configuration

Edit `engine/config.py` to change symbols, risk limits, timeframes, confluence threshold, and dashboard colors. Review every risk setting before enabling `--execute`.

## Offline smoke tests

```powershell
python -m unittest -v test_smoke
```

These tests exercise local indicator and sizing logic. They do not validate Alpaca connectivity, order acceptance, fills, or profitability.
