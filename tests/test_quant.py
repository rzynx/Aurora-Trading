import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paperbot_work"))

from engine.quant import volatility_adjusted_size
from engine.config import MAX_POSITION_PCT


def test_size_is_positive_for_valid_inputs():
    size = volatility_adjusted_size(10_000, 100, 2, risk_pct=0.005)
    assert size > 0
    assert math.isfinite(size)


def test_size_respects_max_position_notional_cap():
    equity, price = 10_000, 100
    size = volatility_adjusted_size(equity, price, 0.01, risk_pct=0.5)
    assert size * price <= equity * MAX_POSITION_PCT + 1e-9


def test_invalid_inputs_fail_closed():
    for values in [
        (0, 100, 2),
        (10_000, 0, 2),
        (10_000, 100, 0),
        (10_000, 100, float("nan")),
        (10_000, 100, -1),
    ]:
        assert volatility_adjusted_size(*values) == 0.0
