"""Offline smoke tests: no API credentials or network access required."""
import unittest
import numpy as np
import pandas as pd
from engine.indicators import add_indicators, detect_regime, detect_fvgs, confluence_score
from engine.quant import volatility_adjusted_size

class SmokeTests(unittest.TestCase):
    def test_indicators_and_regime(self):
        n = 100
        close = np.linspace(100, 110, n)
        df = pd.DataFrame({'open': close-.1, 'high': close+.5, 'low': close-.5,
                           'close': close, 'volume': np.full(n, 1000), 'time': pd.date_range('2026-01-01', periods=n, freq='5min')})
        out = add_indicators(df)
        self.assertIn('atr', out)
        self.assertIn(detect_regime(out)['regime'], ('balanced', 'imbalanced'))

    def test_empty_and_invalid_frames(self):
        self.assertEqual(detect_fvgs(pd.DataFrame()), [])
        self.assertEqual(detect_regime(pd.DataFrame())['regime'], 'unknown')

    def test_size_is_bounded(self):
        qty = volatility_adjusted_size(10000, 100, 2, .01)
        self.assertGreater(qty, 0)
        self.assertLessEqual(qty*100, 2500)
        self.assertEqual(volatility_adjusted_size(0, 100, 2), 0)

    def test_score_range(self):
        score = confluence_score({'regime':'imbalanced','strength':1,'bias':'bullish','atr':1},
                                 [{'type':'bullish','size':.5}], 'bullish', .4)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)

if __name__ == '__main__':
    unittest.main()
