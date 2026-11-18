"""
Orochi Terminal — Professional Glassmorphism Dashboard
Dark + Gold aesthetic, TikTok-ready
Fast load: UI first, scan only on demand
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from engine.config import ACCENT_COLOR, ALL_SYMBOLS

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Orochi Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ====================== GLASSMORPHISM CSS ======================
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp {{
        background: linear-gradient(160deg, #07080C 0%, #0D0F16 40%, #111318 100%);
        font-family: 'Inter', sans-serif;
        color: #E8E6E3;
    }}

    #MainMenu, footer, header, .stDeployButton {{visibility: hidden; display: none;}}

    .glass {{
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(212, 175, 55, 0.18);
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35),
                    inset 0 1px 0 rgba(255, 255, 255, 0.06);
        margin-bottom: 1rem;
    }}

    .glass-strong {{
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(212, 175, 55, 0.28);
        border-radius: 18px;
        padding: 1.5rem;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45),
                    0 0 40px rgba(212, 175, 55, 0.06),
                    inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }}

    h1, h2, h3 {{
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: #F5F2EB !important;
    }}

    .gold {{ color: {ACCENT_COLOR} !important; }}

    .metric-label {{
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: rgba(232, 230, 227, 0.55);
        margin-bottom: 0.25rem;
    }}

    .metric-value {{
        font-size: 1.75rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        color: #F5F2EB;
        line-height: 1.2;
    }}

    .metric-value.gold {{
        color: {ACCENT_COLOR};
        text-shadow: 0 0 24px rgba(212, 175, 55, 0.35);
    }}

    .badge {{
        display: inline-block;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}
    .badge-long {{
        background: rgba(46, 204, 113, 0.15);
        color: #2ecc71;
        border: 1px solid rgba(46, 204, 113, 0.35);
    }}
    .badge-short {{
        background: rgba(231, 76, 60, 0.15);
        color: #e74c3c;
        border: 1px solid rgba(231, 76, 60, 0.35);
    }}
    .badge-none {{
        background: rgba(255, 255, 255, 0.06);
        color: rgba(232, 230, 227, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .badge-imbalanced {{
        background: rgba(212, 175, 55, 0.12);
        color: {ACCENT_COLOR};
        border: 1px solid rgba(212, 175, 55, 0.3);
    }}
    .badge-balanced {{
        background: rgba(52, 152, 219, 0.12);
        color: #3498db;
        border: 1px solid rgba(52, 152, 219, 0.3);
    }}

    .score-bar-bg {{
        height: 6px;
        background: rgba(255,255,255,0.08);
        border-radius: 99px;
        overflow: hidden;
        margin-top: 0.4rem;
    }}
    .score-bar-fill {{
        height: 100%;
        border-radius: 99px;
        background: linear-gradient(90deg, {ACCENT_COLOR}, #F5D76E);
        box-shadow: 0 0 12px rgba(212, 175, 55, 0.5);
    }}

    .stButton > button {{
        background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.08));
        color: {ACCENT_COLOR};
        border: 1px solid rgba(212, 175, 55, 0.4);
        border-radius: 12px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        transition: all 0.2s ease;
        backdrop-filter: blur(8px);
    }}
    .stButton > button:hover {{
        background: linear-gradient(135deg, rgba(212,175,55,0.35), rgba(212,175,55,0.15));
        border-color: {ACCENT_COLOR};
        box-shadow: 0 0 24px rgba(212, 175, 55, 0.25);
        color: #FFF8E7;
    }}

    hr {{
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(212,175,55,0.3), transparent);
        margin: 1.5rem 0;
    }}

    .terminal-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0 1.5rem 0;
    }}
    .logo {{
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        background: linear-gradient(120deg, #F5D76E, {ACCENT_COLOR}, #C9A227);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .status-dot {{
        width: 8px;
        height: 8px;
        background: #2ecc71;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 10px #2ecc71;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}
</style>
""", unsafe_allow_html=True)


# ====================== HELPERS ======================
def metric_card(label: str, value: str, gold: bool = False):
    gold_class = "gold" if gold else ""
    st.markdown(f"""
    <div class="glass">
        <div class="metric-label">{label}</div>
        <div class="metric-value {gold_class}">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def signal_badge(signal: str) -> str:
    if signal == "long":
        return '<span class="badge badge-long">LONG</span>'
    elif signal == "short":
        return '<span class="badge badge-short">SHORT</span>'
    return '<span class="badge badge-none">FLAT</span>'


def regime_badge(regime: str) -> str:
    if regime == "imbalanced":
        return '<span class="badge badge-imbalanced">IMBALANCED</span>'
    elif regime == "balanced":
        return '<span class="badge badge-balanced">BALANCED</span>'
    return '<span class="badge badge-none">—</span>'


def has_keys() -> bool:
    key = os.getenv("ALPACA_API_KEY", "")
    secret = os.getenv("ALPACA_SECRET_KEY", "")
    return bool(key and secret and "your_paper" not in key and "your_paper" not in secret)


def load_account_only():
    """Fast path: only account + positions, no full scan."""
    try:
        from engine.data import get_account, get_positions
        from engine.quant import portfolio_heat, check_daily_loss_limit
        account = get_account()
        heat = portfolio_heat()
        allowed, daily_pnl = check_daily_loss_limit()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "daily_pnl_pct": daily_pnl,
            "allowed": allowed,
            "heat": heat,
        }
    except Exception as e:
        return {"error": str(e)}


# ====================== MAIN ======================
def main():
    # Header — always instant
    st.markdown(f"""
    <div class="terminal-header">
        <div class="logo">⚡ OROCHI TERMINAL</div>
        <div style="font-size:0.85rem; color:rgba(232,230,227,0.6);">
            <span class="status-dot"></span> PAPER · ALPACA · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Key check
    if not has_keys():
        st.markdown("""
        <div class="glass-strong" style="text-align:center; padding:2.5rem;">
            <div style="font-size:1.3rem; margin-bottom:0.8rem;">API Keys Required</div>
            <div style="color:rgba(232,230,227,0.6); margin-bottom:1rem;">
                Add your Alpaca <b>Paper</b> keys to the <code>.env</code> file, then refresh.
            </div>
            <div style="font-family:'JetBrains Mono'; font-size:0.85rem; color:#D4AF37;">
                ALPACA_API_KEY=...<br>ALPACA_SECRET_KEY=...
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Controls
    c1, c2, c3, _ = st.columns([1, 1, 1, 3])
    with c1:
        scan_btn = st.button("Run Full Scan", use_container_width=True)
    with c2:
        exec_btn = st.button("Scan + Execute", use_container_width=True)
    with c3:
        refresh_btn = st.button("Refresh Account", use_container_width=True)

    # Fast account load only
    acct = load_account_only()

    if "error" in acct:
        st.error(f"Account error: {acct['error']}")
        st.info("Check your paper API keys in `.env`")
        st.stop()

    # Top metrics (instant)
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Equity", f"${acct['equity']:,.2f}", gold=True)
    with m2:
        metric_card("Daily P&L", f"{acct['daily_pnl_pct']*100:+.2f}%")
    with m3:
        metric_card("Buying Power", f"${acct['buying_power']:,.0f}")
    with m4:
        metric_card("Open Positions", str(acct["heat"]["num_positions"]))
    with m5:
        metric_card("Portfolio Heat", f"{acct['heat']['heat_pct']*100:.1f}%")

    st.markdown("<hr>", unsafe_allow_html=True)

    left, right = st.columns([1.4, 1])

    # ---- Right column: positions (fast) ----
    with right:
        st.markdown("### Active Positions")
        positions = acct["heat"].get("positions", {})
        if not positions:
            st.markdown("""
            <div class="glass" style="text-align:center; color:rgba(232,230,227,0.4); padding:1.5rem;">
                No open positions
            </div>
            """, unsafe_allow_html=True)
        else:
            html = '<div class="glass-strong">'
            for sym, pos in positions.items():
                pl = pos["unrealized_pl"]
                color = "#2ecc71" if pl >= 0 else "#e74c3c"
                html += f"""
                <div style="display:flex; justify-content:space-between; padding:0.65rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">
                    <div>
                        <div style="font-weight:600; font-family:'JetBrains Mono';">{sym}</div>
                        <div style="font-size:0.75rem; color:rgba(232,230,227,0.5);">{pos['side'].upper()} · {pos['qty']}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'JetBrains Mono'; color:{color};">${pl:+,.2f}</div>
                        <div style="font-size:0.75rem; color:rgba(232,230,227,0.45);">${pos['market_value']:,.0f}</div>
                    </div>
                </div>
                """
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

    # ---- Left column: scan results ----
    with left:
        st.markdown("### Market Scan")

        if scan_btn or exec_btn:
            with st.spinner("Scanning markets (Orochi + ICT + Quant)..."):
                try:
                    from engine.strategy import run_daily_scan
                    results = run_daily_scan(execute=bool(exec_btn))
                    st.session_state["scan_results"] = results
                    st.session_state["last_scan"] = datetime.utcnow().isoformat()
                except Exception as e:
                    st.error(f"Scan failed: {e}")
                    results = []
        else:
            results = st.session_state.get("scan_results", [])

        if not results:
            st.markdown("""
            <div class="glass" style="text-align:center; padding:2rem; color:rgba(232,230,227,0.45);">
                Click <b>Run Full Scan</b> to analyze QQQ, SPY, stocks & crypto<br>
                <span style="font-size:0.8rem;">(Orochi regime · ICT FVG · Quant confluence)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            rows = ""
            for item in sorted(results, key=lambda x: x["confluence"], reverse=True):
                score = item["confluence"]
                rows += f"""
                <div style="display:flex; align-items:center; padding:0.7rem 0; border-bottom:1px solid rgba(255,255,255,0.04);">
                    <div style="width:90px; font-weight:600; font-family:'JetBrains Mono';">{item['symbol']}</div>
                    <div style="width:90px;">{signal_badge(item['signal'])}</div>
                    <div style="width:110px;">{regime_badge(item.get('htf', {}).get('regime', '—'))}</div>
                    <div style="width:80px; font-size:0.85rem; color:rgba(232,230,227,0.7);">{item.get('htf', {}).get('bias', '—')}</div>
                    <div style="flex:1;">
                        <div style="font-size:0.8rem; color:{ACCENT_COLOR}; font-family:'JetBrains Mono';">{score:.2f}</div>
                        <div class="score-bar-bg"><div class="score-bar-fill" style="width:{int(score*100)}%"></div></div>
                    </div>
                    <div style="width:60px; text-align:right; font-size:0.8rem; color:rgba(232,230,227,0.5);">{item.get('sentiment', 0):+.2f}</div>
                </div>
                """

            st.markdown(f"""
            <div class="glass-strong">
                <div style="display:flex; padding-bottom:0.5rem; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.06em; color:rgba(232,230,227,0.4);">
                    <div style="width:90px;">Symbol</div>
                    <div style="width:90px;">Signal</div>
                    <div style="width:110px;">Regime</div>
                    <div style="width:80px;">Bias</div>
                    <div style="flex:1;">Confluence</div>
                    <div style="width:60px; text-align:right;">News</div>
                </div>
                {rows}
            </div>
            """, unsafe_allow_html=True)

            # Top ideas
            tops = [r for r in results if r["signal"] != "none"][:5]
            if tops:
                st.markdown("#### Top Ideas")
                for t in tops:
                    st.markdown(f"""
                    <div class="glass" style="padding:0.8rem 1.2rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:600; font-family:'JetBrains Mono';">{t['symbol']}</span>
                            {signal_badge(t['signal'])}
                        </div>
                        <div style="font-size:0.78rem; color:rgba(232,230,227,0.5); margin-top:0.3rem;">{t.get('reason', '')[:80]}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div style="margin-top:2rem; padding-top:1rem; border-top:1px solid rgba(212,175,55,0.1);
                font-size:0.75rem; color:rgba(232,230,227,0.3); text-align:center;">
        Orochi Framework · ICT FVG · Quant Risk · Paper Trading only · Not financial advice
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
