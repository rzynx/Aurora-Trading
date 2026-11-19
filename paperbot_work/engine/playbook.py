"""Aurora's educational framework for swing trading and long-term investing.

This module is research guidance only. It does not create orders or personalized
investment recommendations. Keep trading and investing portfolios separate.
"""

SWING_TRADING = [
    ("Horizon and objective", "Hold a position for several days to several weeks. Seek a defined price move, not a long-term ownership thesis. Set the expected holding period before entry."),
    ("Market and trend context", "Start with the weekly and daily charts for the primary trend; use 4-hour and 1-hour charts to refine entries. Prefer liquid instruments, clear structure, and adequate average dollar volume."),
    ("Setup quality", "Look for a repeatable setup: trend pullback, breakout with expanding volume, or a well-defined range reversal. Require a clear trigger, invalidation level, and realistic target before considering a trade."),
    ("Catalysts and event risk", "Check earnings dates, guidance, economic releases, central-bank decisions, major company news, and ex-dividend dates. Avoid entering blindly immediately before binary events; gaps can jump over stops."),
    ("Entry and exit plan", "Record entry trigger, stop/invalidation, target, time stop, and what would change the thesis. Do not widen a stop simply to avoid realizing a loss. Consider scaling out only if rules are written in advance."),
    ("Risk and sizing", "Choose dollar risk first, then calculate quantity: risk budget ÷ (entry price − stop price) for a long trade. Include fees, slippage, gaps, and liquidity. Risk small and consistently; correlated positions count as shared exposure."),
    ("Review", "Log the thesis, chart context, catalyst, planned and actual prices, R-multiple, slippage, and rule adherence. Evaluate a meaningful sample after costs; one winning trade proves little."),
]

LONG_TERM_INVESTING = [
    ("Ownership mindset", "Investing means owning a diversified basket of productive assets over years, not reacting to every price tick. Separate the business or asset thesis from short-term market noise."),
    ("Business quality", "For a company, study revenue durability, margins, free cash flow, return on invested capital, competitive advantages, customer concentration, and management's capital allocation."),
    ("Balance sheet and resilience", "Review cash, debt maturities, interest expense, liquidity, dilution, and the ability to survive a downturn. A popular company can still be a poor investment at an excessive price."),
    ("Valuation", "Compare price with normalized earnings, free cash flow, sales, assets, and growth expectations. Use multiple scenarios and a margin of safety; no single multiple proves fair value."),
    ("Portfolio construction", "Diversify across companies, sectors, and asset classes. Monitor concentration, correlations, currency exposure, and liquidity. Avoid allowing one speculative position to dominate portfolio risk."),
    ("Long-term process", "Use a written thesis, target allocation, rebalancing rules, and review schedule. Dollar-cost averaging can help systematize contributions but does not prevent losses or guarantee a profit."),
    ("Evidence and humility", "Distinguish reported facts from forecasts and opinions. Read filings and primary sources where possible. Update a thesis when fundamentals change; do not defend a position because of its purchase price."),
]

DECISION_RULES = [
    ("Classify first", "Label every idea as SWING TRADE or LONG-TERM INVESTMENT. Never mix their time horizons, exits, or performance benchmarks."),
    ("No forced trades", "If data is missing, liquidity is poor, the thesis is unclear, or risk cannot be quantified, return NO ACTION."),
    ("No prediction certainty", "Indicators, news sentiment, analyst estimates, and historical returns are evidence—not certainty. Avoid language such as guaranteed, sure win, or risk-free."),
    ("Backtest honestly", "Use point-in-time data where possible, include delisted assets, costs, spreads, slippage, and realistic fills. Avoid look-ahead bias, survivorship bias, and overfitting. Keep a separate out-of-sample test."),
    ("Paper before live", "Any new rule must be documented, tested, paper-traded, and reviewed before it is considered for deployment. This playbook does not enable live trading."),
    ("Separate books", "Long-term investment holdings should not be liquidated by a swing-trade exit rule. The current Aurora execution engine remains a paper-trading system; this educational playbook does not change its order logic."),
]

