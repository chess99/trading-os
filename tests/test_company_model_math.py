"""手算特例直接调用正式模型使用的函数，不认证其经营假设。"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def catl_engine():
    path = ROOT / "research/companies/CN/300750/models/2026-Q3-engine.py"
    spec = importlib.util.spec_from_file_location("catl_current_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_payer_kernel_covers_losses_before_statutory_reserve():
    model = catl_engine()
    assert "law" in model.run.__code__.co_names
    # 10 profit first offsets 8 opening losses; 10% of the remaining 2 goes
    # to statutory reserve. Cash or a collected receivable is not new profit.
    assert model.law(-8, 0, 20, 10) == pytest.approx((1.8, 0.2, 0.2, 0))
    assert model.law(0, 5, 20, 10) == pytest.approx((9, 6, 1, 0))
    assert model.law(0, 10, 20, 10) == pytest.approx((10, 10, 0, 0))


def test_actual_disposal_kernel_charges_cash_fees_before_gains_tax():
    model = catl_engine()
    assert "sale" in model.run.__code__.co_names
    # Sale proceeds 12, fee 1.2, tax on the 0.8 gain at 25%: common cash 10.6.
    assert model.sale(10, 1.2, 0.1, 0.25) == pytest.approx((10.6, 0.6, 1.2, 0.2))
    # A loss receives no invented immediate tax refund.
    assert model.sale(6, 1, 0.1, 0.25) == pytest.approx((5.4, -0.6, 0.6, 0))
