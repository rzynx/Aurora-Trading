"""Orochi Terminal — institutional-style paper trading dashboard."""
import os
import sys
import calendar
from datetime import datetime, timezone, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="AURORA TRADING | Quant Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit Cloud secrets and local/GitHub environment variables are separate.
try:
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        if not os.getenv(name) and name in st.secrets:
            os.environ[name] = str(st.secrets[name])
except Exception:
    pass

from engine.config import ALL_SYMBOLS
from engine.data import get_account, get_positions, get_bars

BG = "#080D16"
PANEL = "#0D1522"
GRID = "#1C2A3B"
TEXT = "#DCE6F2"
MUTED = "#8292A8"
CYAN = "#35C8E8"
GREEN = "#21C58E"
RED = "#F05D6C"
AMBER = "#E7B85B"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');
:root { color-scheme: dark; }
.stApp { background: #080D16; color: #DCE6F2; font-family: Inter, sans-serif; }
[data-testid="stHeader"] { background: rgba(8,13,22,.92); }
[data-testid="stSidebar"] { background: #0A111D; border-right: 1px solid #1C2A3B; }
[data-testid="stSidebar"] * { color: #DCE6F2; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1800px; padding-top: 1.2rem; padding-bottom: 2rem; }
h1,h2,h3 { letter-spacing: -.035em; color: #EAF2FC !important; }
p, label { color: #A9B8CA; }
div[data-testid="stMetric"] { background: #0D1522; border: 1px solid #1C2A3B; padding: 15px 17px; border-radius: 8px; }
div[data-testid="stMetricLabel"] { color: #8292A8; font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; }
div[data-testid="stMetricValue"] { color: #EAF2FC; font-family: 'IBM Plex Mono', monospace; font-size: 1.55rem; }
div[data-testid="stMetricDelta"] { font-family: 'IBM Plex Mono', monospace; }
.stButton button { background: #102A3A; color: #55D7F0; border: 1px solid #1E5268; border-radius: 5px; font-weight: 600; }
.stButton button:hover { background: #163B50; color: white; border-color: #35C8E8; }
.stTabs [data-baseweb="tab-list"] { gap: 18px; border-bottom: 1px solid #1C2A3B; }
.stTabs [data-baseweb="tab"] { color: #8292A8; }
.stTabs [aria-selected="true"] { color: #35C8E8 !important; }
hr { border-color: #1C2A3B; }
[data-testid="stDataFrame"] { border: 1px solid #1C2A3B; border-radius: 7px; }
.terminal-top { display:flex; justify-content:space-between; align-items:center; padding: 3px 0 16px; border-bottom:1px solid #1C2A3B; margin-bottom:18px; }
.brand { font-size:1.25rem; font-weight:800; letter-spacing:.18em; color:#EAF2FC; }
.brand span { color:#35C8E8; }
.subbrand { color:#8292A8; font: .67rem 'IBM Plex Mono',monospace; letter-spacing:.16em; margin-top:4px; }
.status { color:#21C58E; font: .72rem 'IBM Plex Mono',monospace; letter-spacing:.08em; }
.panel-title { color:#A9B8CA; font:600 .72rem 'IBM Plex Mono',monospace; letter-spacing:.13em; text-transform:uppercase; margin: 8px 0 12px; }
.panel { background:#0D1522; border:1px solid #1C2A3B; border-radius:8px; padding:14px 16px; }
.micro { color:#8292A8; font: .68rem 'IBM Plex Mono',monospace; letter-spacing:.08em; }
.big-number { color:#EAF2FC; font:600 1.6rem 'IBM Plex Mono',monospace; }
div[data-testid="stAlert"] { border-radius:6px; }
</style>
""", unsafe_allow_html=True)


def has_keys():
    return bool(os.getenv("ALPACA_API_KEY", "").strip() and os.getenv("ALPACA_SECRET_KEY", "").strip())


def fmt_money(value):
    return f"${float(value):,.2f}"


def chart_layout(fig, height=320):
    fig.update_layout(
        height=height, paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(color=MUTED, family="IBM Plex Mono, monospace", size=10),
        margin=dict(l=12, r=12, t=18, b=12),
        xaxis=dict(showgrid=False, zeroline=False, color=MUTED),
        yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, color=MUTED),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        hovermode="x unified",
    )
    return fig


def aurora_indicators(bars):
    """Calculate chart indicators without third-party TA dependencies."""
    data = bars.copy()
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    volume = pd.to_numeric(data["volume"], errors="coerce").fillna(0)
    data["EMA9"] = close.ewm(span=9, adjust=False).mean()
    data["EMA21"] = close.ewm(span=21, adjust=False).mean()
    data["EMA50"] = close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    data["RSI14"] = 100 - (100 / (1 + rs))
    data["RSI14"] = data["RSI14"].fillna(50)
    data["MACD"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    data["MACD_SIGNAL"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACD_HIST"] = data["MACD"] - data["MACD_SIGNAL"]
    typical = (high + low + close) / 3
    cumulative_volume = volume.cumsum().replace(0, float("nan"))
    data["VWAP"] = ((typical * volume).cumsum() / cumulative_volume).fillna(close)
    data["BB_MID"] = close.rolling(20, min_periods=10).mean()
    bb_std = close.rolling(20, min_periods=10).std()
    data["BB_UPPER"] = data["BB_MID"] + 2 * bb_std
    data["BB_LOWER"] = data["BB_MID"] - 2 * bb_std
    previous_close = close.shift(1)
    true_range = pd.concat([high - low, (high - previous_close).abs(),
                             (low - previous_close).abs()], axis=1).max(axis=1)
    data["ATR14"] = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_smooth = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_smooth.replace(0, float("nan"))
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_smooth.replace(0, float("nan"))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float("nan"))
    data["ADX14"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    return data


def aurora_candlestick_figure(bars, symbol, title):
    """Adaptive TradingView-style chart: Aurora selects overlays from measured regime."""
    data = aurora_indicators(bars)
    latest = data.iloc[-1]
    adx = float(latest["ADX14"]) if pd.notna(latest["ADX14"]) else 0.0
    ema_spread = abs(float(latest["EMA9"]) - float(latest["EMA21"])) / max(abs(float(latest["close"])), 1e-9)
    trending = adx >= 23 or ema_spread >= 0.002
    regime = "TRENDING" if trending else "RANGE / MEAN-REVERSION"
    selected = "EMA 9/21/50 + MACD" if trending else "Bollinger Bands + RSI"
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.025,
                        row_heights=[.56, .16, .14, .14],
                        subplot_titles=("PRICE / AURORA OVERLAYS", "RSI 14", "MACD 12·26·9", "VOLUME"))
    fig.add_trace(go.Candlestick(
        x=data["time"], open=data["open"], high=data["high"], low=data["low"],
        close=data["close"], name=symbol, increasing_line_color=GREEN,
        decreasing_line_color=RED, increasing_fillcolor=GREEN,
        decreasing_fillcolor=RED,
    ), row=1, col=1)
    if trending:
        for column, color, label in (
            ("EMA9", "#F2C14E", "EMA 9"),
            ("EMA21", "#35C8E8", "EMA 21"),
            ("EMA50", "#B58CFF", "EMA 50"),
        ):
            fig.add_trace(go.Scatter(x=data["time"], y=data[column], mode="lines",
                name=label, line=dict(color=color, width=1.25)), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=data["time"], y=data["BB_UPPER"], mode="lines",
            name="Bollinger upper", line=dict(color="#B58CFF", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=data["time"], y=data["BB_LOWER"], mode="lines",
            name="Bollinger lower", line=dict(color="#B58CFF", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(181,140,255,.07)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data["time"], y=data["BB_MID"], mode="lines",
            name="Bollinger basis", line=dict(color="#B58CFF", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data["time"], y=data["VWAP"], mode="lines",
        name="VWAP", line=dict(color=AMBER, width=1.4, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=data["time"], y=data["RSI14"], mode="lines",
        name="RSI 14", line=dict(color="#B58CFF", width=1.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color=RED, opacity=.65, row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=GREEN, opacity=.65, row=2, col=1)
    fig.add_trace(go.Bar(x=data["time"], y=data["MACD_HIST"], name="MACD histogram",
        marker_color=[GREEN if value >= 0 else RED for value in data["MACD_HIST"].fillna(0)]), row=3, col=1)
    fig.add_trace(go.Scatter(x=data["time"], y=data["MACD"], mode="lines",
        name="MACD", line=dict(color=CYAN, width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=data["time"], y=data["MACD_SIGNAL"], mode="lines",
        name="MACD signal", line=dict(color=AMBER, width=1.1)), row=3, col=1)
    fig.add_trace(go.Bar(x=data["time"], y=data["volume"], name="Volume",
        marker_color="rgba(53,200,232,.42)"), row=4, col=1)
    fig.update_layout(
        title=title, height=760, paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(color=MUTED, family="IBM Plex Mono, monospace", size=9),
        margin=dict(l=12, r=12, t=55, b=12), xaxis_rangeslider_visible=False,
        hovermode="x unified", legend=dict(orientation="h", y=1.04, x=0),
    )
    for axis in ("xaxis", "xaxis2", "xaxis3", "xaxis4"):
        fig.update_layout(**{axis: dict(showgrid=False, color=MUTED)})
    for axis in ("yaxis", "yaxis2", "yaxis3", "yaxis4"):
        fig.update_layout(**{axis: dict(showgrid=True, gridcolor=GRID, color=MUTED)})
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    return fig, regime, selected, adx, float(latest["RSI14"]), float(latest["ATR14"]) if pd.notna(latest["ATR14"]) else 0.0


@st.cache_data(ttl=300)
def get_equity_history():
    """Fetch broker-sourced equity history; return None if endpoint/data unavailable."""
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        client = __import__("engine.data", fromlist=["_clients"])._clients()[0]
        request = GetPortfolioHistoryRequest(period="1M", timeframe="1D")
        history = client.get_portfolio_history(request)
        ts = getattr(history, "timestamp", None) or []
        equity = getattr(history, "equity", None) or []
        if ts is None or equity is None or len(ts) == 0 or len(equity) == 0:
            return None
        frame = pd.DataFrame({"time": pd.to_datetime(ts, unit="s", utc=True), "equity": pd.to_numeric(equity)})
        return frame.dropna()
    except Exception:
        return None


def get_daily_pnl_history():
    """Fetch broker-reported daily profit/loss observations from Alpaca."""
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        client = __import__('engine.data', fromlist=['_clients'])._clients()[0]
        history = client.get_portfolio_history(GetPortfolioHistoryRequest(period='1A', timeframe='1D'))
        timestamps = getattr(history, 'timestamp', None) or []
        profits = getattr(history, 'profit_loss', None) or []
        if not timestamps or len(timestamps) != len(profits):
            return pd.DataFrame(columns=['date', 'pnl'])
        frame = pd.DataFrame({
            'date': pd.to_datetime(timestamps, unit='s', utc=True).tz_convert('America/New_York').date,
            'pnl': pd.to_numeric(profits, errors='coerce'),
        }).dropna().sort_values('date')
        return frame.groupby('date', as_index=False)['pnl'].sum()
    except Exception as exc:
        print('[dashboard] Daily P&L history unavailable:', exc)
        return pd.DataFrame(columns=['date', 'pnl'])


def render_pnl_calendar():
    st.markdown('### DAILY P&L CALENDAR')
    st.caption('Green = profitable session · red = losing session · blank = no reported P&L.')
    frame = get_daily_pnl_history()
    if frame.empty:
        st.warning('Alpaca has not returned daily portfolio history for this account yet.')
        return
    values = {row['date']: float(row['pnl']) for _, row in frame.iterrows()}
    chosen = st.date_input('Choose month', value=date.today().replace(day=1), key='orochi_pnl_month')
    year, month = chosen.year, chosen.month
    monthly = sum(v for d, v in values.items() if d.year == year and d.month == month)
    profitable = sum(1 for d, v in values.items() if d.year == year and d.month == month and v > 0.005)
    losing = sum(1 for d, v in values.items() if d.year == year and d.month == month and v < -0.005)
    a, b, c = st.columns(3)
    a.metric('MONTHLY P&L', fmt_money(monthly), f'{profitable} green · {losing} red sessions')
    b.metric('PROFITABLE DAYS', profitable)
    c.metric('LOSING DAYS', losing)
    st.markdown('### ' + calendar.month_name[month] + ' ' + str(year))
    labels = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    header = st.columns(7, gap='medium')
    for col, label in zip(header, labels):
        col.markdown('**' + label + '**')
    for week in calendar.monthcalendar(year, month):
        cols = st.columns(7, gap='medium')
        for col, day_number in zip(cols, week):
            if not day_number:
                col.markdown('<div style="height:76px;margin-bottom:8px"></div>', unsafe_allow_html=True)
                continue
            value = values.get(date(year, month, day_number))
            bg, fg, detail = '#0D1522', '#8292A8', ''
            if value is not None and value > 0.005:
                bg, fg, detail = 'rgba(33,197,142,.18)', '#21C58E', f'+${value:,.2f}'
            elif value is not None and value < -0.005:
                bg, fg, detail = 'rgba(240,93,108,.18)', '#F05D6C', f'-${abs(value):,.2f}'
            html = (
                f'<div style="height:76px;margin-bottom:8px;background:{bg};border:1px solid #1C2A3B;border-radius:7px;padding:9px 5px;text-align:center">'
                f'<b>{day_number}</b><div style="color:{fg};font-size:11px;margin-top:7px">{detail}</div></div>'
            )
            col.markdown(html, unsafe_allow_html=True)
    st.caption('Monthly P&L is the sum of the daily P&L values returned by Alpaca. Blank dates have no reported session P&L.')


@st.cache_data(ttl=300)
def load_quant_returns():
    """Build aligned daily return series from real Alpaca bars."""
    frames, missing = {}, []
    for symbol in ALL_SYMBOLS:
        bars = get_bars(symbol, '1Day', limit=90)
        if bars is None or bars.empty or len(bars) < 8:
            missing.append(symbol)
            continue
        idx = pd.to_datetime(bars['time'], utc=True)
        series = pd.Series(bars['close'].astype(float).values, index=idx).sort_index()
        frames[symbol] = series.pct_change()
    if not frames:
        return pd.DataFrame(), missing
    returns = pd.concat(frames, axis=1).sort_index().tail(60)
    return returns.dropna(axis=1, thresh=8), missing

def quant_heatmap(matrix, title, zmin=-1, zmax=1):
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
        zmin=zmin, zmax=zmax, zmid=0, colorscale="RdBu",
        text=[[f"{v:.2f}" if pd.notna(v) else "—" for v in row] for row in matrix.values],
        texttemplate="%{text}", textfont={"size": 10},
        colorbar={"tickfont": {"color": MUTED}, "thickness": 10},
        hovertemplate="%{y} × %{x}<br>%{z:.3f}<extra></extra>",
    ))
    fig.update_layout(title={"text": title, "font": {"size": 12, "color": TEXT}},
        height=max(350, 38 * len(matrix.index) + 100), paper_bgcolor=PANEL,
        plot_bgcolor=PANEL, font={"family": "IBM Plex Mono, monospace", "color": MUTED, "size": 10},
        margin={"l": 15, "r": 15, "t": 48, "b": 20}, xaxis={"side": "bottom", "tickangle": -35},
        yaxis={"autorange": "reversed"})
    return fig


@st.cache_data(ttl=20)
def load_market_floor():
    """Latest Alpaca one-minute bars; snapshots refresh every 20 seconds."""
    rows, unavailable = [], []
    for symbol in ALL_SYMBOLS:
        bars = get_bars(symbol, "1Min", limit=3)
        if bars is None or len(bars) < 1:
            unavailable.append(symbol)
            continue
        last = bars.iloc[-1]
        previous = bars.iloc[-2] if len(bars) > 1 else None
        price = float(last["close"])
        prior = float(previous["close"]) if previous is not None else price
        change = ((price / prior) - 1) * 100 if prior else 0.0
        rows.append({
            "SYMBOL": symbol, "LAST": price, "1M CHANGE %": change,
            "1M VOLUME": float(last["volume"]),
            "BAR TIME (UTC)": pd.to_datetime(last["time"], utc=True).strftime("%H:%M:%S"),
        })
    return pd.DataFrame(rows), unavailable


@st.cache_data(ttl=20)
def load_market_floor_candles(symbol):
    """Recent one-minute OHLCV bars for the Market Floor candlestick chart."""
    bars = get_bars(symbol, "1Min", limit=60)
    if bars is None or bars.empty:
        return pd.DataFrame()
    return bars.copy()


def render_market_floor():
    st.markdown('<div class="panel-title">09 / MARKET FLOOR · LIVE TAPE</div>', unsafe_allow_html=True)
    st.caption("Real Alpaca market data · one-minute OHLCV candles · refreshes automatically every 30 seconds. This is a market-data monitor, not a direct NYSE exchange-floor feed.")
    frame, unavailable = load_market_floor()
    if frame.empty:
        st.warning("No latest bars returned. Check Alpaca market-data access and feed availability.")
    else:
        frame = frame.sort_values("1M CHANGE %", ascending=False)
        gainers = int((frame["1M CHANGE %"] > 0).sum())
        losers = int((frame["1M CHANGE %"] < 0).sum())
        unchanged = int((frame["1M CHANGE %"] == 0).sum())
        a, b, c, d = st.columns(4)
        a.metric("INSTRUMENTS REPORTING", len(frame))
        b.metric("ADVANCING", gainers)
        c.metric("DECLINING", losers)
        d.metric("UNCHANGED", unchanged)
        st.dataframe(frame, use_container_width=True, hide_index=True,
            column_config={
                "LAST": st.column_config.NumberColumn(format="$%.4f"),
                "1M CHANGE %": st.column_config.NumberColumn(format="%.3f%%"),
                "1M VOLUME": st.column_config.NumberColumn(format="%,.0f"),
            })
        fig = go.Figure(go.Bar(x=frame["SYMBOL"], y=frame["1M CHANGE %"],
            marker_color=[GREEN if v >= 0 else RED for v in frame["1M CHANGE %"]],
            hovertemplate="%{x}<br>1m change: %{y:.3f}%<extra></extra>"))
        fig.update_layout(title="ONE-MINUTE MARKET BREADTH", height=280,
            paper_bgcolor=PANEL, plot_bgcolor=PANEL,
            font={"family":"IBM Plex Mono, monospace","color":MUTED,"size":10},
            margin={"l":15,"r":15,"t":45,"b":20}, yaxis={"gridcolor":GRID,"ticksuffix":"%"})
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="panel-title">CANDLESTICK TAPE · 1-MINUTE OHLC</div>', unsafe_allow_html=True)
        candle_symbol = st.selectbox("Candlestick instrument", list(ALL_SYMBOLS), key="market_floor_candle_symbol")
        candle_bars = load_market_floor_candles(candle_symbol)
        if candle_bars.empty:
            st.warning(f"No one-minute OHLC bars returned for {candle_symbol}.")
        else:
            candle_fig, regime, selected_indicators, adx, rsi, atr = aurora_candlestick_figure(
                candle_bars, candle_symbol, f"{candle_symbol} · 60 × 1-MINUTE CANDLES")
            st.plotly_chart(candle_fig, use_container_width=True,
                            config={"displayModeBar": True, "displaylogo": False})
            st.caption(f"AURORA REGIME: {regime} · AUTO-SELECTED: {selected_indicators} · ADX {adx:.1f} · RSI {rsi:.1f} · ATR {atr:.4f}")
        st.caption("Latest bar timestamps are UTC. When the market is closed, timestamps and prices will be stale until the next session.")
    if unavailable:
        st.caption("No recent bar returned for: " + ", ".join(unavailable))




@st.cache_data(ttl=20)
def load_live_tracker_data():
    """Cache broker market/position snapshot to avoid duplicate API calls on reruns."""
    live_positions = get_positions()
    symbols = list(dict.fromkeys(list(ALL_SYMBOLS) + list(live_positions.keys())))
    rows, unavailable = [], []
    for symbol in symbols:
        bars = get_bars(symbol, "1Min", limit=3)
        if bars is None or bars.empty:
            unavailable.append(symbol)
            continue
        last = bars.iloc[-1]
        previous = bars.iloc[-2] if len(bars) > 1 else None
        price = float(last["close"])
        prior = float(previous["close"]) if previous is not None else price
        change = ((price / prior) - 1) * 100 if prior else 0.0
        position = live_positions.get(symbol)
        rows.append({
            "SYMBOL": symbol,
            "LAST PRICE": price,
            "1M CHANGE %": change,
            "VOLUME": float(last["volume"]),
            "POSITION": "LONG" if position and float(position.qty) > 0 else ("SHORT" if position else "—"),
            "QTY": float(position.qty) if position else 0.0,
            "UNREALIZED P&L": float(position.unrealized_pl) if position else None,
            "P&L %": float(position.unrealized_plpc) * 100 if position else None,
            "BAR TIME (UTC)": pd.to_datetime(last["time"], utc=True).strftime("%H:%M:%S"),
        })
    return pd.DataFrame(rows), unavailable


def render_live_tracker():
    """Refreshable main-screen market and open-position monitor."""
    st.markdown('<div class="panel-title">LIVE TRACKER · MARKET TAPE + OPEN POSITIONS</div>', unsafe_allow_html=True)
    st.caption("Broker-sourced Alpaca one-minute bars and current paper positions · refreshes every 30 seconds.")
    try:
        frame, unavailable = load_live_tracker_data()
        if frame.empty:
            st.warning("No live bars returned. Check Alpaca market-data access.")
            return
        open_rows = frame[frame["POSITION"] != "—"]
        gainers = int((frame["1M CHANGE %"] > 0).sum())
        decliners = int((frame["1M CHANGE %"] < 0).sum())
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("SYMBOLS TRACKED", len(frame))
        k2.metric("ADVANCING", gainers)
        k3.metric("DECLINING", decliners)
        k4.metric("OPEN POSITIONS", len(open_rows))
        frame = frame.sort_values(["POSITION", "1M CHANGE %"], ascending=[True, False])
        st.dataframe(frame, use_container_width=True, hide_index=True,
            column_config={
                "LAST PRICE": st.column_config.NumberColumn(format="$%.4f"),
                "1M CHANGE %": st.column_config.NumberColumn(format="%.3f%%"),
                "VOLUME": st.column_config.NumberColumn(format="%,.0f"),
                "QTY": st.column_config.NumberColumn(format="%.4f"),
                "UNREALIZED P&L": st.column_config.NumberColumn(format="$%.2f"),
                "P&L %": st.column_config.NumberColumn(format="%.2f%%"),
            })
        if unavailable:
            st.caption("No recent bar: " + ", ".join(unavailable))
        st.caption("Prices update when Alpaca returns new bars. This is a market/position monitor, not a live order-fill tape; timestamps are UTC.")
    except Exception as exc:
        st.warning(f"Live tracker temporarily unavailable: {exc}")




def render_crypto_kalshi_tracker():
    """Near-live crypto tape paired with Kalshi's event-contract probabilities."""
    st.markdown('<div class="panel-title">CRYPTO INTELLIGENCE · LIVE SPOT + KALSHI CONSENSUS</div>', unsafe_allow_html=True)
    st.caption("Spot prices use Alpaca one-minute crypto bars. Prediction probabilities come from Kalshi's public YES quotes; they describe each contract's outcome, not a guaranteed coin-price forecast.")

    st.markdown('<div class="panel-title">AURORA AUTONOMOUS CRYPTO EXECUTION · PAPER ONLY</div>', unsafe_allow_html=True)
    st.caption("Aurora scans BTC, ETH, SOL and XRP, ranks qualified long setups by confluence, and can submit at most ONE paper buy per click. It will stand aside if no setup passes the existing strategy and risk checks. New short positions remain disabled.")
    if st.button("AURORA · SCAN + EXECUTE BEST CRYPTO SETUP", key="aurora_crypto_execute", use_container_width=True):
        with st.spinner("Aurora is analyzing crypto regimes, multi-timeframe structure and risk..."):
            try:
                from engine.config import CRYPTO_SYMBOLS
                from engine.strategy import run_daily_scan
                from engine.data import get_positions
                account_check = get_account()
                account_status = str(getattr(getattr(account_check, "status", "unknown"), "value", getattr(account_check, "status", "unknown"))).split(".")[-1].lower()
                if account_status != "active" or bool(getattr(account_check, "trading_blocked", False)):
                    st.session_state["aurora_crypto_execution"] = {"status": "BLOCKED — paper account is not active or trading is blocked", "symbol": "—", "score": None}
                else:
                    candidates = run_daily_scan(symbols=CRYPTO_SYMBOLS, execute=False)
                    open_positions = get_positions()
                    def already_open(symbol):
                        base = symbol.split("/")[0]
                        return symbol in open_positions or base in open_positions or (base + "USD") in open_positions
                    eligible = [item for item in candidates if item.get("signal") == "long" and not already_open(item.get("symbol", ""))]
                    eligible.sort(key=lambda item: float(item.get("confluence", 0)), reverse=True)
                    if not eligible:
                        st.session_state["aurora_crypto_execution"] = {"status": "NO TRADE — no unheld crypto long setup passed Aurora's filters", "symbol": "—", "score": None}
                    else:
                        chosen = eligible[0]
                        execution = run_daily_scan(symbols=[chosen["symbol"]], execute=True, max_new_entries=1)
                        outcome = execution[0] if execution else {}
                        st.session_state["aurora_crypto_execution"] = {
                            "status": outcome.get("execution_status", "NO ORDER CONFIRMATION"),
                            "symbol": chosen["symbol"], "score": float(chosen.get("confluence", 0)),
                            "order_id": outcome.get("order_id", "—"),
                        }
            except Exception as exc:
                st.session_state["aurora_crypto_execution"] = {"status": f"ERROR — {exc}", "symbol": "—", "score": None}
    execution_result = st.session_state.get("aurora_crypto_execution")
    if execution_result:
        status = execution_result.get("status", "Unknown")
        st.info(f"AURORA RESULT · {status} · ASSET {execution_result.get('symbol', '—')} · CONFLUENCE {execution_result.get('score') if execution_result.get('score') is not None else '—'} · ORDER {execution_result.get('order_id', '—')}")

    from engine.kalshi import fetch_crypto_markets
    crypto_symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"]
    price_rows, price_frames = [], {}
    for symbol in crypto_symbols:
        bars = get_bars(symbol, "1Min", limit=60)
        if bars is None or bars.empty:
            continue
        price_frames[symbol] = bars
        last = bars.iloc[-1]
        previous = bars.iloc[-2] if len(bars) > 1 else None
        price = float(last["close"])
        prior = float(previous["close"]) if previous is not None else price
        move = ((price / prior) - 1) * 100 if prior else 0.0
        price_rows.append({"ASSET": symbol.split("/")[0], "SPOT PRICE": price,
                           "1M CHANGE %": move, "BAR TIME UTC": pd.to_datetime(last["time"], utc=True).strftime("%H:%M:%S")})
    if price_rows:
        st.dataframe(pd.DataFrame(price_rows), use_container_width=True, hide_index=True,
            column_config={"SPOT PRICE": st.column_config.NumberColumn(format="$%,.4f"),
                           "1M CHANGE %": st.column_config.NumberColumn(format="%+.3f%%")})
    else:
        st.warning("No Alpaca crypto bars returned. Check crypto market-data access.")
    market_rows, errors = fetch_crypto_markets()
    if market_rows:
        market_frame = pd.DataFrame(market_rows)
        market_frame["KALSHI SIGNAL"] = market_frame["YES PROBABILITY"].apply(
            lambda p: "YES FAVORED" if p is not None and p >= 0.55 else ("NO FAVORED" if p is not None and p <= 0.45 else ("NEUTRAL" if p is not None else "NO QUOTE"))
        )
        market_frame["YES IMPLIED PROBABILITY %"] = market_frame["YES PROBABILITY"].apply(
            lambda p: round(float(p) * 100, 2) if p is not None and pd.notna(p) else None
        )
        market_frame = market_frame.sort_values(["COIN", "YES PROBABILITY"], ascending=[True, False], na_position="last")
        st.dataframe(market_frame.drop(columns=["YES PROBABILITY"]), use_container_width=True, hide_index=True,
            column_config={
                "YES IMPLIED PROBABILITY %": st.column_config.ProgressColumn("YES IMPLIED PROBABILITY", min_value=0, max_value=100, format="%.1f%%"),
                "VOLUME 24H": st.column_config.NumberColumn(format="%,.0f"),
            })
        selected = st.selectbox("Crypto chart", crypto_symbols, key="kalshi_crypto_chart")
        chart_bars = price_frames.get(selected)
        if chart_bars is not None and not chart_bars.empty:
            fig, regime, selected_indicators, adx, rsi, atr = aurora_candlestick_figure(
                chart_bars, selected, f"{selected} · 60 × 1-MINUTE CANDLES")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})
            st.caption(f"AURORA REGIME: {regime} · AUTO-SELECTED: {selected_indicators} · ADX {adx:.1f} · RSI {rsi:.1f} · ATR {atr:.4f}")
        st.caption("Signal labels describe the Kalshi contract's YES/NO pricing only. They are not a standalone buy/sell recommendation. YES probability uses the bid/ask midpoint where available, otherwise the last traded YES price or bid.")
    else:
        st.warning("No open crypto contracts were found in the configured Kalshi series. Series availability can change; this panel will retry on its next refresh.")
    if errors:
        st.caption("Some Kalshi series could not be read: " + ", ".join(errors))



def safe_account_snapshot():
    account = get_account()
    positions = get_positions()
    from engine.quant import portfolio_heat, check_daily_loss_limit
    heat = portfolio_heat()
    allowed, daily_pnl = check_daily_loss_limit()
    return account, positions, heat, allowed, daily_pnl



def render_trade_intelligence(positions):
    """Desk blotter: broker order states, live position P&L, scan thesis and news evidence."""
    st.markdown('<div class="panel-title">EXECUTION INTELLIGENCE · PAPER TRADE BLOTTER</div>', unsafe_allow_html=True)
    try:
        from engine.data import get_recent_orders
        orders = get_recent_orders(limit=35)
    except Exception as exc:
        orders = []
        st.warning(f"Broker order history unavailable: {exc}")
    try:
        pos_by_symbol = get_positions()
    except Exception:
        pos_by_symbol = dict(positions or {})
    if orders:
        rows = []
        for order in orders:
            symbol = order.get("symbol", "")
            base = symbol.replace("/USD", "")
            position = pos_by_symbol.get(symbol) or pos_by_symbol.get(base) or pos_by_symbol.get(base + "USD")
            rows.append({
                "TIME (UTC)": str(order.get("filled_at") or order.get("submitted_at") or "—")[:19],
                "ASSET": symbol, "SIDE": order.get("side"), "ORDER STATUS": order.get("status"),
                "ORDER QTY": order.get("qty"), "FILLED QTY": order.get("filled_qty"),
                "AVG FILL": order.get("filled_avg_price") or None,
                "MARK": float(position.current_price) if position else None,
                "OPEN P&L": float(position.unrealized_pl) if position else None,
                "P&L %": float(position.unrealized_plpc) * 100 if position else None,
                "ORDER ID": order.get("id", "")[:12],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
            column_config={
                "ORDER QTY": st.column_config.NumberColumn(format="%.6f"),
                "FILLED QTY": st.column_config.NumberColumn(format="%.6f"),
                "AVG FILL": st.column_config.NumberColumn(format="$%.4f"),
                "MARK": st.column_config.NumberColumn(format="$%.4f"),
                "OPEN P&L": st.column_config.NumberColumn(format="$%.2f"),
                "P&L %": st.column_config.NumberColumn(format="%.2f%%"),
            })
        st.caption("Open P&L is the broker's unrealized P&L for a currently held asset. A dash means no matching open position; realized P&L for closed round trips is not reconstructed here.")
    else:
        st.info("No recent broker orders found. Orders appear here after Aurora submits them through the paper account.")

    focus_symbol = orders[0].get("symbol") if orders else (next(iter(pos_by_symbol), None))
    if focus_symbol:
        st.markdown(f'<div class="panel-title">TRADE FOCUS · {focus_symbol} · LIVE MARKET CONTEXT</div>', unsafe_allow_html=True)
        bars = get_bars(focus_symbol, "5Min", limit=120)
        if bars is not None and not bars.empty:
            fig, regime, indicators, adx, rsi, atr = aurora_candlestick_figure(
                bars, focus_symbol, f"{focus_symbol} · 5-MINUTE TRADE CONTEXT")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})
            st.caption(f"REGIME {regime} · INDICATORS {indicators} · ADX {adx:.1f} · RSI {rsi:.1f} · ATR {atr:.4f}")
        else:
            st.caption("No recent market bars returned for this trade focus.")

    scan = st.session_state.get("orochi_scan", [])
    if scan:
        st.markdown('<div class="panel-title">AURORA DECISION BRIEF · SIGNAL EVIDENCE</div>', unsafe_allow_html=True)
        decision_rows = []
        for item in sorted(scan, key=lambda x: float(x.get("confluence", 0)), reverse=True)[:10]:
            decision_rows.append({
                "ASSET": item.get("symbol"), "SIGNAL": str(item.get("signal", "none")).upper(),
                "CONFLUENCE": float(item.get("confluence", 0)),
                "HTF BIAS": item.get("htf", {}).get("bias", "—"),
                "NEWS SENTIMENT": float(item.get("sentiment", 0)),
                "HEADLINES": int(item.get("news_count", 0)),
                "DECISION / REASON": item.get("reason", ""),
                "EXECUTION": item.get("execution_status", "ANALYSIS ONLY"),
            })
        st.dataframe(pd.DataFrame(decision_rows), use_container_width=True, hide_index=True)
        headline_rows = []
        for item in scan:
            for headline in item.get("news_headlines", []):
                headline_rows.append((item.get("symbol"), headline))
        if headline_rows:
            st.markdown('<div class="panel-title">NEWS READ BY AURORA · LAST SCAN</div>', unsafe_allow_html=True)
            seen = set()
            for symbol, headline in headline_rows[:12]:
                title = headline.get("headline", "").strip()
                url = headline.get("url", "")
                key = (symbol, title)
                if not title or key in seen:
                    continue
                seen.add(key)
                source = headline.get("source", "News feed")
                timestamp = headline.get("created_at") or "time unavailable"
                st.markdown(f"**{symbol} · {source}** · {timestamp}\n\n" +
                            (f"[{title}]({url})" if url else title))
    else:
        st.caption("Run a strategy scan or paper execution to populate Aurora's decision evidence and news panel.")


def main():
    now = datetime.now(timezone.utc)
    st.markdown(f"""
    <div class="terminal-top">
      <div><div class="brand"><span>◈</span> AURORA <span style="color:#8292A8;font-weight:500">QUANT TERMINAL</span></div>
      <div class="subbrand">SYSTEMATIC STRATEGIES · EXECUTION MONITOR · RISK CONTROL</div></div>
      <div style="text-align:right"><div class="status">● PAPER BROKER LINK</div>
      <div class="micro">{now.strftime('%d %b %Y  %H:%M:%S')} UTC</div></div>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## ◈ CONTROL")
        st.caption("AURORA / PAPER ENVIRONMENT")
        workspace = st.radio("WORKSPACE", ["TRADING DESK", "P&L CALENDAR"], key="orochi_workspace")
        st.divider()
        refresh_seconds = st.selectbox("Refresh interval", ["Manual", "30 seconds", "60 seconds"], index=0)
        selected_symbol = st.selectbox("Chart instrument", list(ALL_SYMBOLS), index=0)
        timeframe = st.selectbox("Chart timeframe", ["5Min", "15Min", "1Hour", "1Day"], index=1)
        st.divider()
        st.markdown("**SYSTEM GUARDRAILS**")
        st.caption("Paper endpoint enforced in engine")
        st.caption("Daily loss lock · −$1,100")
        st.caption("Daily profit stop · +$1,100,000")
        st.caption("Max concurrent positions · 3")
        st.caption("Risk budget · 0.5% / trade")
        if st.button("↻ REFRESH DATA", use_container_width=True):
            st.rerun()

    if not has_keys():
        st.error("BROKER CREDENTIALS NOT FOUND")
        st.info("The dashboard needs Alpaca Paper keys in Streamlit Cloud → App settings → Secrets (or local environment variables). GitHub Actions secrets do not automatically populate Streamlit.")
        st.stop()

    try:
        account, positions, heat, allowed, daily_pnl = safe_account_snapshot()
    except Exception as exc:
        st.error(f"BROKER CONNECTION ERROR · {exc}")
        st.stop()

    if workspace == "P&L CALENDAR":
        render_pnl_calendar()
        st.stop()

    equity = float(account.equity)
    last_equity = float(account.last_equity)
    day_change = equity - last_equity
    day_pct = daily_pnl * 100
    st.markdown('<div class="panel-title">01 / ACCOUNT OVERVIEW</div>', unsafe_allow_html=True)
    m = st.columns(6)
    m[0].metric("Net liquidation", fmt_money(equity), f"{day_pct:+.2f}% today")
    m[1].metric("Day P&L", fmt_money(day_change), f"{day_pct:+.2f}%")
    m[2].metric("Cash", fmt_money(account.cash))
    m[3].metric("Buying power", fmt_money(account.buying_power))
    m[4].metric("Open positions", str(len(positions)), f"of 3 max")
    m[5].metric("Gross exposure", f"{heat['heat_pct']*100:.1f}%", "portfolio heat")

    daily_lock_reason = ("DAILY LOSS LOCK · −$1,100 reached" if day_change <= -1100 else
                         "DAILY PROFIT TARGET · +$1,100,000 reached" if day_change >= 1100000 else
                         "RISK CHECK UNAVAILABLE" if not allowed else "")
    if not allowed:
        st.warning(f"DAILY RISK LOCK ACTIVE — {daily_lock_reason or 'risk verification failed'}. New entries are blocked; exit management remains available.")
    raw_status = getattr(account, "status", "unknown")
    broker_status = str(getattr(raw_status, "value", raw_status)).split(".")[-1].strip().lower()
    trading_blocked = bool(getattr(account, "trading_blocked", False))
    if broker_status != "active" or trading_blocked:
        st.error("BROKER ACCOUNT STATUS REQUIRES ATTENTION")
        st.write(f"Alpaca status: **{raw_status}** · Trading blocked: **{trading_blocked}**")
    else:
        st.success("BROKER ACCOUNT HEALTHY · ACTIVE · TRADING UNBLOCKED")

    tabs = st.tabs(["DESK OVERVIEW", "MARKET ANALYTICS", "QUANT LAB / HEATMAPS", "MARKET FLOOR", "POSITIONS", "RISK & CONTROLS", "CRYPTO / KALSHI PREDICTIONS"])
    with tabs[0]:
        @st.fragment(run_every="30s")
        def trade_intelligence_fragment():
            render_trade_intelligence(positions)
        trade_intelligence_fragment()
        st.markdown('<div class="panel-title">SESSION P&L CONTROL · DAILY HARD LIMITS</div>', unsafe_allow_html=True)
        p1, p2, p3 = st.columns(3)
        p1.metric("SESSION P&L", fmt_money(day_change), f"{day_pct:+.2f}% vs prior close")
        p2.metric("PROFIT STOP", "$1,100,000", "new entries lock at target")
        p3.metric("MAX DAILY LOSS", "−$1,100", "new entries lock at floor")
        if day_change >= 0:
            target_progress = min(day_change / 1100000.0, 1.0)
            st.progress(target_progress, text=f"Profit target progress · {target_progress*100:.4f}%")
        else:
            loss_progress = min(abs(day_change) / 1100.0, 1.0)
            st.progress(loss_progress, text=f"Daily loss-limit usage · {loss_progress*100:.1f}%")
        if not allowed:
            st.error(daily_lock_reason or "Risk verification unavailable — execution locked.")

        @st.fragment(run_every="30s")
        def live_tracker_fragment():
            render_live_tracker()
        live_tracker_fragment()

        st.markdown(f'<div class="panel-title">02A / DESK MARKET STRUCTURE · {selected_symbol}</div>', unsafe_allow_html=True)
        desk_bars = get_bars(selected_symbol, timeframe, limit=180)
        if desk_bars is not None and not desk_bars.empty:
            desk_fig, desk_regime, desk_indicators, desk_adx, desk_rsi, desk_atr = aurora_candlestick_figure(
                desk_bars, selected_symbol, f"{selected_symbol} · {timeframe} · AURORA DESK CHART")
            st.plotly_chart(desk_fig, use_container_width=True,
                            config={"displayModeBar": True, "displaylogo": False})
            st.caption(f"AURORA REGIME: {desk_regime} · AUTO-SELECTED: {desk_indicators} · ADX {desk_adx:.1f} · RSI {desk_rsi:.1f} · ATR {desk_atr:.4f}")
        else:
            st.warning("No market bars returned for the Desk Overview chart. Check the selected instrument and Alpaca data access.")

        left, right = st.columns([1.7, 1])
        with left:
            st.markdown('<div class="panel-title">02 / EQUITY CURVE · BROKER HISTORY</div>', unsafe_allow_html=True)
            history = get_equity_history()
            if history is not None and not history.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=history["time"], y=history["equity"], mode="lines", name="Account equity",
                    line=dict(color=CYAN, width=2), fill="tozeroy", fillcolor="rgba(53,200,232,.08)"))
                chart_layout(fig, 340)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Broker equity history is unavailable right now. Live account values above are still sourced directly from Alpaca.")
        with right:
            st.markdown('<div class="panel-title">03 / EXPOSURE MATRIX</div>', unsafe_allow_html=True)
            exposure = [heat.get("long_exposure", 0), heat.get("short_exposure", 0)]
            fig = go.Figure(go.Bar(x=exposure, y=["LONG", "SHORT"], orientation="h",
                marker_color=[GREEN, RED], text=[fmt_money(x) for x in exposure], textposition="auto"))
            chart_layout(fig, 150)
            fig.update_layout(showlegend=False, xaxis_title="Market value (USD)")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('<div class="panel-title">RISK UTILIZATION</div>', unsafe_allow_html=True)
            st.progress(min(max(float(heat["heat_pct"]), 0), 1.0), text=f"Gross exposure · {heat['heat_pct']*100:.1f}%")
            st.caption("Strategy entry cap: 75% gross exposure.")

        st.markdown('<div class="panel-title">04 / STRATEGY SCANNER</div>', unsafe_allow_html=True)
        a, b, c = st.columns([1, 1, 3])
        with a:
            scan_clicked = st.button("RUN SCAN", use_container_width=True)
        with b:
            execute_clicked = st.button("SCAN + PAPER EXECUTE", use_container_width=True, disabled=not allowed)
        if scan_clicked or execute_clicked:
            with st.spinner("Analyzing configured universe · multi-timeframe / FVG / confluence..."):
                try:
                    from engine.strategy import run_daily_scan
                    st.session_state["orochi_scan"] = run_daily_scan(execute=bool(execute_clicked))
                    st.session_state["orochi_scan_time"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                except Exception as exc:
                    st.error(f"Scan failed: {exc}")
        results = st.session_state.get("orochi_scan", [])
        if results:
            scan_df = pd.DataFrame([{
                "SYMBOL": x.get("symbol"), "SIGNAL": str(x.get("signal", "none")).upper(),
                "CONFLUENCE": round(float(x.get("confluence", 0)), 3),
                "HTF BIAS": x.get("htf", {}).get("bias", "—"),
                "REGIME": x.get("htf", {}).get("regime", "—"),
                "NEWS SENTIMENT": x.get("sentiment", 0), "HEADLINES": x.get("news_count", 0),
                "MODEL NOTE": x.get("reason", ""), "EXECUTION": x.get("execution_status", "ANALYSIS ONLY")
            } for x in sorted(results, key=lambda z: z.get("confluence", 0), reverse=True)])
            st.dataframe(scan_df, use_container_width=True, hide_index=True)
            st.caption("Last scan: " + st.session_state.get("orochi_scan_time", "—") + " · Scanner results are analysis, not guaranteed trade signals.")
        else:
            st.caption("No scan stored in this session. Run a scan to populate the signal matrix.")

    with tabs[1]:
        st.markdown(f'<div class="panel-title">05 / {selected_symbol} · {timeframe} MARKET STRUCTURE</div>', unsafe_allow_html=True)
        bars = get_bars(selected_symbol, timeframe, limit=180)
        if bars is not None and not bars.empty:
            fig, regime, selected_indicators, adx, rsi, atr = aurora_candlestick_figure(
                bars, selected_symbol, f"{selected_symbol} · {timeframe} · AURORA TECHNICAL MAP")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})
            st.caption(f"AURORA REGIME: {regime} · AUTO-SELECTED: {selected_indicators} · ADX {adx:.1f} · RSI {rsi:.1f} · ATR {atr:.4f}")
            latest = bars.iloc[-1]
            quote_cols = st.columns(4)
            quote_cols[0].metric("Last close", fmt_money(latest["close"]))
            quote_cols[1].metric("Bar high", fmt_money(latest["high"]))
            quote_cols[2].metric("Bar low", fmt_money(latest["low"]))
            quote_cols[3].metric("Volume", f"{latest['volume']:,.0f}")
        else:
            st.warning("No market bars returned for this instrument/timeframe.")
        st.caption("Market data is supplied by Alpaca. Stock feed availability depends on your account/data entitlement.")


    with tabs[2]:
        st.markdown('<div class="panel-title">06 / CROSS-ASSET QUANT RESEARCH</div>', unsafe_allow_html=True)
        st.caption("Calculated from historical Alpaca daily bars. Descriptive analytics, not forecasts.")
        with st.spinner("Loading daily history and calculating cross-asset statistics..."):
            returns, missing_symbols = load_quant_returns()
        if returns.empty or returns.shape[1] < 2:
            st.warning("Not enough overlapping market history to calculate cross-asset matrices.")
        else:
            corr = returns.corr(min_periods=8)
            st.markdown('<div class="panel-title">06A / PEARSON RETURN CORRELATION</div>', unsafe_allow_html=True)
            st.plotly_chart(quant_heatmap(corr, "DAILY RETURN CORRELATION"), use_container_width=True, config={"displayModeBar": False})
            st.caption("−1 = move oppositely · 0 = weak linear relationship · +1 = move together.")

            st.markdown('<div class="panel-title">06B / REALIZED VOLATILITY HEATMAP</div>', unsafe_allow_html=True)
            vol = pd.DataFrame({f"{w}D": returns.tail(w).std() * (252 ** 0.5) * 100 for w in (5, 10, 20)}).T
            vf = go.Figure(go.Heatmap(z=vol.values, x=list(vol.columns), y=list(vol.index),
                colorscale="Turbo", text=[[f"{v:.1f}%" if pd.notna(v) else "—" for v in row] for row in vol.values],
                texttemplate="%{text}", textfont={"size": 11}, colorbar={"title": "Ann. %"},
                hovertemplate="%{y} realized vol<br>%{x}: %{z:.2f}%<extra></extra>"))
            vf.update_layout(height=250, paper_bgcolor=PANEL, plot_bgcolor=PANEL,
                font={"family":"IBM Plex Mono, monospace","color":MUTED,"size":10}, margin={"l":15,"r":15,"t":20,"b":15})
            st.plotly_chart(vf, use_container_width=True, config={"displayModeBar": False})
            st.caption("Annualized standard deviation of daily returns; short windows are noisy.")

            st.markdown('<div class="panel-title">06C / MOMENTUM MATRIX</div>', unsafe_allow_html=True)
            momentum = pd.DataFrame({
                "1D": returns.iloc[-1] * 100,
                "5D": ((1 + returns.tail(5)).prod() - 1) * 100,
                "20D": ((1 + returns.tail(20)).prod() - 1) * 100,
            }).T
            mf = go.Figure(go.Heatmap(z=momentum.values, x=list(momentum.columns), y=list(momentum.index),
                zmid=0, colorscale="RdYlGn",
                text=[[f"{v:+.2f}%" if pd.notna(v) else "—" for v in row] for row in momentum.values],
                texttemplate="%{text}", textfont={"size":11}, colorbar={"title":"Return %"},
                hovertemplate="%{y} return<br>%{x}: %{z:.2f}%<extra></extra>"))
            mf.update_layout(height=240, paper_bgcolor=PANEL, plot_bgcolor=PANEL,
                font={"family":"IBM Plex Mono, monospace","color":MUTED,"size":10}, margin={"l":15,"r":15,"t":20,"b":15})
            st.plotly_chart(mf, use_container_width=True, config={"displayModeBar": False})

            st.markdown('<div class="panel-title">06D / RETURN & DRAWDOWN STATISTICS</div>', unsafe_allow_html=True)
            wealth = (1 + returns.tail(20).fillna(0)).cumprod()
            drawdown = (wealth / wealth.cummax() - 1).min() * 100
            stats = pd.DataFrame({
                "OBSERVATIONS": returns.count(),
                "MEAN DAILY RETURN %": returns.mean() * 100,
                "DAILY VOL %": returns.std() * 100,
                "WORST DAY %": returns.min() * 100,
                "BEST DAY %": returns.max() * 100,
                "20D MAX DRAWDOWN %": drawdown,
            }).round(3).reset_index(names="SYMBOL")
            st.dataframe(stats, use_container_width=True, hide_index=True)
            if missing_symbols:
                st.caption("Insufficient history / unavailable symbols: " + ", ".join(missing_symbols))

    with tabs[3]:
        @st.fragment(run_every="30s")
        def market_floor_fragment():
            render_market_floor()
        market_floor_fragment()

    with tabs[4]:
        st.markdown('<div class="panel-title">07 / OPEN BOOK · LIVE BROKER POSITIONS</div>', unsafe_allow_html=True)
        if positions:
            rows = []
            for symbol, p in positions.items():
                rows.append({"SYMBOL": symbol, "SIDE": "LONG" if float(p.qty) > 0 else "SHORT",
                    "QTY": float(p.qty), "AVG ENTRY": float(p.avg_entry_price), "MARK": float(p.current_price),
                    "MARKET VALUE": float(p.market_value), "UNREALIZED P&L": float(p.unrealized_pl),
                    "P&L %": float(p.unrealized_plpc)*100})
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True,
                column_config={"UNREALIZED P&L": st.column_config.NumberColumn(format="$%.2f"),
                               "MARKET VALUE": st.column_config.NumberColumn(format="$%.2f"),
                               "AVG ENTRY": st.column_config.NumberColumn(format="$%.4f"),
                               "MARK": st.column_config.NumberColumn(format="$%.4f"),
                               "P&L %": st.column_config.NumberColumn(format="%.2f%%")})
        else:
            st.info("No open positions in the paper account.")
        st.caption("Positions are read directly from the Alpaca paper account. This panel does not submit orders.")

    with tabs[6]:
        @st.fragment(run_every="30s")
        def crypto_kalshi_fragment():
            render_crypto_kalshi_tracker()
        crypto_kalshi_fragment()

    with tabs[5]:
        st.markdown('<div class="panel-title">08 / RISK ENGINE TELEMETRY</div>', unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        r1.metric("Daily risk lock", "ARMED" if allowed else "TRIPPED", f"{fmt_money(day_change)} session P&L")
        r2.metric("Gross exposure", f"{heat['heat_pct']*100:.2f}%", "target ceiling 75%")
        r3.metric("Risk per trade", "0.50%", "configured budget")
        risk_rows = [
            {"CONTROL": "Paper-only broker client", "STATE": "ENFORCED"},
            {"CONTROL": "Daily loss hard lock", "STATE": "−$1,100"},
            {"CONTROL": "Daily profit stop", "STATE": "+$1,100,000"},
            {"CONTROL": "Maximum concurrent positions", "STATE": "3"},
            {"CONTROL": "Maximum position allocation", "STATE": "10.00%"},
            {"CONTROL": "Short entries", "STATE": "DISABLED"},
            {"CONTROL": "Protective broker-side stop orders", "STATE": "NOT IMPLEMENTED"},
        ]
        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)
        st.warning("Important: the current automated exit monitor checks positions periodically; it is not a guaranteed broker-hosted stop-loss. Do not treat this paper system as production-ready or connect live funds.")

    st.markdown("---")
    st.caption(f"AURORA TRADING · PAPER ENVIRONMENT · DATA SNAPSHOT {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · NOT FINANCIAL ADVICE")


if __name__ == "__main__":
    main()
