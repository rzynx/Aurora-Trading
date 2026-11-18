"""
Orochi Terminal — real-market-data research dashboard.
Paper-only: this UI does not submit orders.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from engine.config import ACCENT_COLOR, ALL_SYMBOLS
from engine.data import get_bars

st.set_page_config(page_title="Orochi | Quant Terminal", page_icon="⚡", layout="wide",
                   initial_sidebar_state="collapsed")

BG = "#090B10"
PANEL = "#11151E"
GOLD = "#D4AF37"
MUTED = "#8993A5"
GREEN = "#27D99A"
RED = "#FF5D73"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&display=swap');
:root { color-scheme: dark; }
.stApp { background: radial-gradient(ellipse at 20% 0%, #171b29 0%, #090b10 48%); color:#e8ebf2; font-family:Inter,sans-serif; }
#MainMenu, footer, header, .stDeployButton {visibility:hidden;}
.block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1600px;}
h1,h2,h3 {letter-spacing:-.035em;}
[data-testid="stMetric"] {background:linear-gradient(145deg,#151a25,#0e121a);border:1px solid #252c39;padding:14px 16px;border-radius:12px;}
[data-testid="stMetricLabel"] {color:#8993a5;}
[data-testid="stMetricValue"] {font-family:'DM Mono',monospace;}
.stButton>button {background:#1b1b19;color:#e5c65b;border:1px solid #6d5b25;border-radius:9px;font-weight:600;}
.stButton>button:hover {border-color:#e5c65b;color:#fff2bd;}
div[data-testid="stSelectbox"] label, div[data-testid="stRadio"] label {color:#aab3c2;}
hr {border-color:#252c39;}
.eyebrow {font:11px 'DM Mono',monospace;letter-spacing:.16em;color:#9aa4b5;text-transform:uppercase;}
.brand {font-size:26px;font-weight:800;letter-spacing:-1.3px;color:#f0d77c;}
.panel {background:linear-gradient(145deg,rgba(21,26,37,.96),rgba(13,17,25,.96));border:1px solid #252c39;border-radius:14px;padding:15px 18px;}
.small {font:11px 'DM Mono',monospace;color:#8792a4;}
@media(max-width:700px){.block-container{padding-left:1rem;padding-right:1rem}.brand{font-size:21px}}
</style>
""", unsafe_allow_html=True)

def add_technicals(frame):
    d = frame.copy().sort_values("time")
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["ema200"] = d.close.ewm(span=200, adjust=False).mean()
    typical = (d.high + d.low + d.close) / 3
    # Rolling VWAP approximation over the visible bar window; explicitly labelled.
    d["vwap"] = (typical * d.volume).rolling(30, min_periods=1).sum() / d.volume.rolling(30, min_periods=1).sum().replace(0, np.nan)
    mid = d.close.rolling(20).mean()
    std = d.close.rolling(20).std()
    d["bb_mid"], d["bb_upper"], d["bb_lower"] = mid, mid + 2*std, mid - 2*std
    delta = d.close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    ema12 = d.close.ewm(span=12, adjust=False).mean()
    ema26 = d.close.ewm(span=26, adjust=False).mean()
    d["macd"] = ema12 - ema26
    d["macd_signal"] = d.macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d.macd - d.macd_signal
    tr = pd.concat([d.high-d.low, (d.high-d.close.shift()).abs(), (d.low-d.close.shift()).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    return d

@st.cache_data(ttl=45, show_spinner=False)
def load_bars(symbol, timeframe, limit=250):
    return get_bars(symbol, timeframe=timeframe, limit=limit)

@st.cache_data(ttl=300, show_spinner=False)
def correlation_data(symbols):
    series = []
    for sym in symbols:
        bars = get_bars(sym, timeframe="1Day", limit=45)
        if bars is None or bars.empty:
            continue
        dates = pd.to_datetime(bars.time, utc=True).dt.floor("D")
        s = pd.Series(bars.close.to_numpy(), index=dates, name=sym).groupby(level=0).last().pct_change()
        series.append(s)
    if len(series) < 2:
        return pd.DataFrame()
    return pd.concat(series, axis=1, join="inner").dropna().corr()

def money(value):
    return f"${value:,.2f}" if pd.notna(value) else "—"

# Header
head_l, head_r = st.columns([2.2, 1])
with head_l:
    st.markdown('<div class="eyebrow">SYSTEMATIC RESEARCH / PAPER ENVIRONMENT</div><div class="brand">⚡ OROCHI <span style="color:#8c95a5;font-weight:500">TERMINAL</span></div>', unsafe_allow_html=True)
with head_r:
    st.markdown(f'<div style="text-align:right;padding-top:8px" class="small">LOCAL UI CLOCK · {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC<br><span style="color:#e3c65e">● PAPER MODE · ORDER ROUTING DISABLED</span></div>', unsafe_allow_html=True)

st.divider()
if not (os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")):
    try:
        _ = st.secrets["ALPACA_API_KEY"]
        _ = st.secrets["ALPACA_SECRET_KEY"]
    except Exception:
        st.warning("Market data credentials are not configured in this deployment. Add Alpaca PAPER credentials in Streamlit Secrets to load your account and authenticated data.")
        
# Controls
ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1, 1])
with ctrl1:
    symbol = st.selectbox("INSTRUMENT", ALL_SYMBOLS, index=0)
with ctrl2:
    timeframe = st.selectbox("BAR INTERVAL", ["5Min", "15Min", "1Hour", "1Day"], index=1)
with ctrl3:
    if st.button("↻  REFRESH MARKET DATA", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner(f"Loading {symbol} · {timeframe} bars from Alpaca…"):
    raw = load_bars(symbol, timeframe, 250)

if raw is None or raw.empty:
    st.error("No bars returned for this instrument/interval. Check credentials, market session, symbol support, and provider status. No synthetic data is substituted.")
else:
    d = add_technicals(raw)
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    change = (float(last.close) / float(prev.close) - 1) * 100 if float(prev.close) else 0
    source = "ALPACA CRYPTO DATA" if "/" in symbol else "ALPACA IEX EQUITIES FEED · NOT SIP"
    age = (datetime.now(timezone.utc) - pd.to_datetime(last.time).to_pydatetime()).total_seconds()/60
    age_label = f"{age:.0f} min old" if age < 1440 else f"{age/60:.1f} hours old"
    freshness = "LATEST AVAILABLE BAR" if age < (20 if timeframe in ("5Min","15Min") else 180) else "STALE / DELAYED BAR"
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("LAST CLOSE", money(last.close), f"{change:+.2f}%")
    m2.metric("RSI · 14", f"{last.rsi:.1f}" if pd.notna(last.rsi) else "—")
    m3.metric("ATR · 14", money(last.atr14))
    m4.metric("EMA 20 / 50", f"{last.ema20:.2f} / {last.ema50:.2f}")
    m5.metric("BAR AGE", age_label, freshness)
    st.markdown(f'<div class="small" style="margin:4px 0 12px">SOURCE: {source} &nbsp;·&nbsp; LAST BAR: {pd.to_datetime(last.time).strftime("%Y-%m-%d %H:%M:%S %Z")} &nbsp;·&nbsp; {len(d)} BARS</div>', unsafe_allow_html=True)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.035,
                        row_heights=[.68,.16,.16], subplot_titles=("PRICE / STRUCTURE", "VOLUME", "RSI · MACD"))
    fig.add_trace(go.Candlestick(x=d.time, open=d.open, high=d.high, low=d.low, close=d.close,
                                 name=symbol, increasing_line_color=GREEN, decreasing_line_color=RED), row=1,col=1)
    for col, label, color, width in [
        ("ema20","EMA 20","#f2cc60",1.2),("ema50","EMA 50","#58a6ff",1.2),
        ("ema200","EMA 200","#c792ea",1.2),("vwap","Rolling VWAP","#f08c46",1.1),
        ("bb_upper","Bollinger Upper","#667085",.8),("bb_lower","Bollinger Lower","#667085",.8)]:
        fig.add_trace(go.Scatter(x=d.time,y=d[col],name=label,line=dict(color=color,width=width),opacity=.9),row=1,col=1)
    fig.add_trace(go.Bar(x=d.time,y=d.volume,name="Volume",marker_color=np.where(d.close>=d.open,GREEN,RED),opacity=.55),row=2,col=1)
    fig.add_trace(go.Scatter(x=d.time,y=d.rsi,name="RSI",line=dict(color="#c792ea",width=1.3)),row=3,col=1)
    fig.add_hline(y=70,line_dash="dot",line_color="#6b7280",row=3,col=1)
    fig.add_hline(y=30,line_dash="dot",line_color="#6b7280",row=3,col=1)
    fig.add_trace(go.Scatter(x=d.time,y=d.macd,name="MACD",line=dict(color="#58a6ff",width=1)),row=3,col=1)
    fig.add_trace(go.Scatter(x=d.time,y=d.macd_signal,name="MACD Signal",line=dict(color="#f2cc60",width=1)),row=3,col=1)
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=BG,
                      height=760, margin=dict(l=8,r=8,t=45,b=8), xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h",y=1.03,x=0),font=dict(family="DM Mono",size=10,color="#aab3c2"),
                      hovermode="x unified")
    fig.update_yaxes(gridcolor="#222936",zerolinecolor="#222936")
    fig.update_xaxes(gridcolor="#1b2230")
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo":False,"scrollZoom":True})

    # Quant diagnostics based only on retrieved bars
    st.markdown("### QUANT DIAGNOSTICS")
    q1,q2,q3,q4 = st.columns(4)
    bars_per_day = {"5Min": 78, "15Min": 26, "1Hour": 6.5, "1Day": 1}[timeframe]
    realized = d.close.pct_change().dropna().std() * np.sqrt(252 * bars_per_day) * 100
    q1.metric("REALIZED VOL · APPROX", f"{realized:.2f}%" if pd.notna(realized) else "—")
    q2.metric("BOLLINGER WIDTH", f"{((last.bb_upper-last.bb_lower)/last.bb_mid*100):.2f}%" if pd.notna(last.bb_mid) and last.bb_mid else "—")
    q3.metric("PRICE VS VWAP", f"{(last.close/last.vwap-1)*100:+.2f}%" if pd.notna(last.vwap) and last.vwap else "—")
    trend = "BULL STACK" if last.close>last.ema20>last.ema50 else ("BEAR STACK" if last.close<last.ema20<last.ema50 else "MIXED")
    q4.metric("EMA STRUCTURE", trend)

st.divider()
st.markdown("### CROSS-ASSET CORRELATION")
st.caption("Pearson correlation of overlapping daily close-to-close returns. Values are calculated from retrieved provider bars; unavailable pairs are not filled with estimates.")
with st.spinner("Retrieving daily bars for correlation matrix…"):
    corr = correlation_data(["SPY","QQQ","NVDA","TSLA","BTC/USD","ETH/USD"])
if corr.empty:
    st.info("Correlation matrix unavailable: insufficient overlapping daily observations from the data provider.")
else:
    heat = go.Figure(data=go.Heatmap(z=corr.values,x=corr.columns,y=corr.index,zmin=-1,zmax=1,
                                    colorscale=[[0,"#e45b6b"],[.5,"#202938"],[1,"#39c99a"]],
                                    text=np.round(corr.values,2),texttemplate="%{text:.2f}",
                                    hovertemplate="%{y} × %{x}: %{z:.3f}<extra></extra>"))
    heat.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor=BG,
                       height=420,margin=dict(l=8,r=8,t=10,b=8),font=dict(family="DM Mono",size=11,color="#aab3c2"))
    st.plotly_chart(heat,use_container_width=True,config={"displaylogo":False})

st.divider()
st.markdown("### PAPER SCANNER")
st.caption("Research scan only. Automated order execution is intentionally disabled in this dashboard draft.")
if st.button("RUN FULL SCAN", type="primary"):
    with st.spinner("Analyzing configured watchlist…"):
        try:
            from engine.strategy import run_daily_scan
            results = run_daily_scan(execute=False)
            st.session_state["orochi_scan_results"] = results
            st.session_state["orochi_scan_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception as exc:
            st.error(f"Scan failed: {exc}")
results = st.session_state.get("orochi_scan_results", [])
if results:
    table = pd.DataFrame([{
        "SYMBOL": x.get("symbol"), "SIGNAL": str(x.get("signal","")).upper(),
        "CONFLUENCE": x.get("confluence"), "REGIME": x.get("htf",{}).get("regime"),
        "BIAS": x.get("htf",{}).get("bias"), "NEWS SENTIMENT": x.get("sentiment")
    } for x in results]).sort_values("CONFLUENCE",ascending=False)
    st.dataframe(table,use_container_width=True,hide_index=True)
    st.caption("Last scan: " + st.session_state.get("orochi_scan_time","unknown"))

st.markdown('<div class="small" style="text-align:center;padding:24px 0 8px">OROCHI RESEARCH TERMINAL · REAL PROVIDER DATA ONLY · PAPER MODE · NO ORDER EXECUTION</div>',unsafe_allow_html=True)
