<div align="center">
  <img src="paperbot_work/dashboard/assets/aurora-logo.svg" alt="AURORA TRADING" width="760" />
  <h1>AURORA TRADING</h1>
  <p><strong>Systematic strategies · Execution monitoring · Risk control</strong></p>
  <p>Institutional-inspired trading research terminal.</p>
</div>

---

## Overview

AURORA is trading dashboard and research workspace built around market data, adaptive technical analysis, news context, trade monitoring, and risk controls.

## Features

- Candlestick charts with adaptive technical overlays
- EMA, RSI, MACD, VWAP, Bollinger Bands, ATR, and ADX analytics
- Strategy scans with news sentiment context
- Paper order blotter and open-position monitoring
- Daily paper-account risk guardrails
- Streamlit dashboard designed for desktop and mobile browsers

## Run locally

From the repository root:

```bash
cd paperbot_work
python -m pip install -r requirements.txt
streamlit run dashboard/app.py
```

Configure Alpaca **paper-trading** credentials as environment variables or Streamlit secrets:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Never commit API keys or secrets. Use a paper account; this project is for research and simulation, not financial advice or production execution.

## Project layout

- `paperbot_work/dashboard/` — Streamlit interface
- `paperbot_work/engine/` — market data, strategy, and risk logic
- `paperbot_work/auto_trader.py` — scheduled paper-trading runner
