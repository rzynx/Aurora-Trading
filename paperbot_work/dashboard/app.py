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
    page_title="OROCHI | Quant Terminal",
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


def render_market_floor():
    st.markdown('<div class="panel-title">09 / MARKET FLOOR · LIVE TAPE</div>', unsafe_allow_html=True)
    st.caption("Real Alpaca market data · latest one-minute bars · refreshes automatically every 30 seconds. This is a market-data monitor, not a direct NYSE exchange-floor feed.")
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
            fig = go.Figure(go.Scatter(x=chart_bars["time"], y=chart_bars["close"], mode="lines",
                line={"color": CYAN, "width": 2}, name=selected))
            chart_layout(fig, 300)
            fig.update_layout(title=f"{selected} · LAST 60 ONE-MINUTE BARS")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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


def main():
    now = datetime.now(timezone.utc)
    st.markdown(f"""
    <div class="terminal-top">
      <div><div class="brand"><span>◈</span> OROCHI <span style="color:#8292A8;font-weight:500">QUANT TERMINAL</span></div>
      <div class="subbrand">SYSTEMATIC STRATEGIES · EXECUTION MONITOR · RISK CONTROL</div></div>
      <div style="text-align:right"><div class="status">● PAPER BROKER LINK</div>
      <div class="micro">{now.strftime('%d %b %Y  %H:%M:%S')} UTC</div></div>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## ◈ CONTROL")
        st.caption("OROCHI / PAPER ENVIRONMENT")
        workspace = st.radio("WORKSPACE", ["TRADING DESK", "P&L CALENDAR"], key="orochi_workspace")
        st.divider()
        refresh_seconds = st.selectbox("Refresh interval", ["Manual", "30 seconds", "60 seconds"], index=0)
        selected_symbol = st.selectbox("Chart instrument", list(ALL_SYMBOLS), index=0)
        timeframe = st.selectbox("Chart timeframe", ["5Min", "15Min", "1Hour", "1Day"], index=1)
        st.divider()
        st.markdown("**SYSTEM GUARDRAILS**")
        st.caption("Paper endpoint enforced in engine")
        st.caption("Daily loss breaker · 2%")
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

    if not allowed:
        st.warning("RISK LOCK ACTIVE — daily loss threshold reached or risk verification failed. New entries are blocked.")
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
        def live_tracker_fragment():
            render_live_tracker()
        live_tracker_fragment()

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
                "SENTIMENT": x.get("sentiment", 0), "MODEL NOTE": x.get("reason", "")
            } for x in sorted(results, key=lambda z: z.get("confluence", 0), reverse=True)])
            st.dataframe(scan_df, use_container_width=True, hide_index=True)
            st.caption("Last scan: " + st.session_state.get("orochi_scan_time", "—") + " · Scanner results are analysis, not guaranteed trade signals.")
        else:
            st.caption("No scan stored in this session. Run a scan to populate the signal matrix.")

    with tabs[1]:
        st.markdown(f'<div class="panel-title">05 / {selected_symbol} · {timeframe} MARKET STRUCTURE</div>', unsafe_allow_html=True)
        bars = get_bars(selected_symbol, timeframe, limit=180)
        if bars is not None and not bars.empty:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.04, row_heights=[.75, .25])
            fig.add_trace(go.Candlestick(x=bars["time"], open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"],
                name=selected_symbol, increasing_line_color=GREEN, decreasing_line_color=RED), row=1, col=1)
            fig.add_trace(go.Bar(x=bars["time"], y=bars["volume"], name="Volume", marker_color="rgba(53,200,232,.45)"), row=2, col=1)
            fig.update_layout(height=560, paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=MUTED, family="IBM Plex Mono"),
                margin=dict(l=10,r=10,t=15,b=10), xaxis_rangeslider_visible=False, showlegend=False)
            fig.update_xaxes(gridcolor=GRID)
            fig.update_yaxes(gridcolor=GRID)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})
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
        r1.metric("Daily loss breaker", "ARMED" if allowed else "TRIPPED", f"{day_pct:+.2f}% day")
        r2.metric("Gross exposure", f"{heat['heat_pct']*100:.2f}%", "target ceiling 75%")
        r3.metric("Risk per trade", "0.50%", "configured budget")
        risk_rows = [
            {"CONTROL": "Paper-only broker client", "STATE": "ENFORCED"},
            {"CONTROL": "Daily loss threshold", "STATE": "2.00%"},
            {"CONTROL": "Maximum concurrent positions", "STATE": "3"},
            {"CONTROL": "Maximum position allocation", "STATE": "10.00%"},
            {"CONTROL": "Short entries", "STATE": "DISABLED"},
            {"CONTROL": "Protective broker-side stop orders", "STATE": "NOT IMPLEMENTED"},
        ]
        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)
        st.warning("Important: the current automated exit monitor checks positions periodically; it is not a guaranteed broker-hosted stop-loss. Do not treat this paper system as production-ready or connect live funds.")

    st.markdown("---")
    st.caption(f"OROCHI QUANT TERMINAL · PAPER TRADING ONLY · DATA SNAPSHOT {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · NOT FINANCIAL ADVICE")


if __name__ == "__main__":
    main()
