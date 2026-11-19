"""
Orochi + ICT Paper Trading Bot - Configuration
"""

# ============== SYMBOLS ==============
# QQQ = NQ proxy (Alpaca has no futures)
CORE_SYMBOLS = ["QQQ", "SPY"]

STOCK_WATCHLIST = [
    "AAPL", "NVDA", "TSLA", "META", "AMZN", "MSFT"
]

CRYPTO_SYMBOLS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"
]

ALL_SYMBOLS = CORE_SYMBOLS + STOCK_WATCHLIST + CRYPTO_SYMBOLS

# ============== RISK ==============
RISK_PER_TRADE = 0.0025         # 0.25% per trade = $250 at $100k equity
MAX_OPEN_POSITIONS = 2
DAILY_LOSS_LIMIT_DOLLARS = 500.0    # 0.5% of $100k starting equity
DAILY_PROFIT_TARGET_DOLLARS = 1000.0  # 1.0% daily gain lock
MAX_POSITION_PCT = 0.05          # Max 5% of equity in one name

# ============== TIMEFRAMES ==============
# Primary analysis timeframes
HTF = "1Hour"                   # Higher timeframe bias
MTF = "15Min"                   # Intermediate
LTF = "5Min"                    # Entry timeframe

# ============== OROCHI / REGIME ==============
VWAP_LOOKBACK = 20
ATR_PERIOD = 14
REGIME_VOL_THRESHOLD = 1.3      # Above this ATR multiple = imbalanced

# ============== ICT FVG ==============
FVG_MIN_SIZE_ATR = 0.15         # Minimum FVG size as fraction of ATR
FVG_LOOKBACK_BARS = 50

# ============== QUANT ==============
VOL_LOOKBACK = 20
MIN_CONFLUENCE_SCORE = 0.62     # Aggressive threshold

# ============== NEWS ==============
NEWS_LOOKBACK_HOURS = 18
NEGATIVE_SENTIMENT_THRESHOLD = -0.25

# ============== UI ==============
ACCENT_COLOR = "#D4AF37"        # Gold
BG_COLOR = "#0B0C10"
GLASS_BG = "rgba(255, 255, 255, 0.05)"
GLASS_BORDER = "rgba(212, 175, 55, 0.25)"