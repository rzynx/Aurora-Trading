# Orochi Terminal

Professional paper trading system combining:

- **Orochi-inspired** market regime detection (Auction Market Theory lite)
- **ICT Fair Value Gaps** for precise entries
- **Basic Quantitative Finance** (volatility-adjusted sizing, risk controls, confluence scoring)
- **News sentiment** filter
- Dark **glassmorphism** dashboard with gold accents (TikTok-ready)

Built for **Alpaca Paper Trading**.

---

## Quick Start

### 1. Install

```bash
cd orochi_bot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API Keys

```bash
cp .env.example .env
# Edit .env and put your Alpaca **Paper** API keys
```

Get paper keys: https://app.alpaca.markets/paper/dashboard/overview

### 3. Run the Dashboard (recommended)

```bash
streamlit run dashboard/app.py
```

### 4. Or run a one-shot CLI scan

```bash
python run_scan.py              # analysis only
python run_scan.py --execute    # analysis + place paper orders
```

---

## Features

| Module | What it does |
|--------|--------------|
| **Regime** | Detects balanced vs imbalanced conditions using VWAP distance + ATR |
| **FVG** | Finds unmitigated ICT Fair Value Gaps on 15m |
| **Confluence** | Scores setups 0–1 (regime + FVG + HTF bias + news) |
| **Quant** | 1.5% risk per trade, ATR-based stops, daily loss circuit breaker |
| **Multi-asset** | QQQ (NQ proxy), SPY, mega-cap stocks, BTC/ETH/SOL/XRP |
| **UI** | Dark glassmorphism + gold, designed to look expensive on camera |

---

## Configuration

Edit `engine/config.py`:

- `RISK_PER_TRADE = 0.015` (1.5%)
- `MIN_CONFLUENCE_SCORE = 0.62` (aggressive)
- `STOCK_WATCHLIST` / `CRYPTO_SYMBOLS`
- Gold accent already set

---

## Important Notes

- **No real futures**: Alpaca does not support NQ. We use **QQQ** as the Nasdaq proxy.
- Paper trading only. Never put live keys in `.env` while testing.
- Free IEX data is used. For denser data consider Alpaca paid plans later.
- News sentiment is basic (TextBlob). Can be upgraded later.

---

## Future Roadmap

- Web API wrapper (FastAPI) → easy iOS / web app
- Better volume profile / orderflow approximations
- Trade journal + expectancy dashboard
- Alerts (Telegram / Discord)

---

*Not financial advice. For education and paper trading only.*
