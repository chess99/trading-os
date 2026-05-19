"""Tests for RiskManager sub-checks: sector limit, circuit breaker, VaR."""
from unittest.mock import MagicMock


def _make_portfolio(positions=None):
    """Minimal Portfolio mock with positions and mark_to_market."""
    port = MagicMock()
    port.positions = positions or {}
    port.mark_to_market = lambda prices: sum(
        pos.shares * prices.get(sym, pos.avg_cost)
        for sym, pos in port.positions.items()
    ) + 1_000_000  # 100万现金
    return port


def _make_position(shares, avg_cost):
    pos = MagicMock()
    pos.shares = shares
    pos.avg_cost = avg_cost
    return pos


def _make_signal(symbol, action, size=0.05):
    from trading_os.strategy.base import Signal
    return Signal(symbol=symbol, action=action, size=size)


# ── Sector classification ──────────────────────────────────────────────────────

def test_get_sector_sse_688_is_kechuang():
    from trading_os.risk.manager import _get_sector
    assert _get_sector("SSE:688123") == "科创板"


def test_get_sector_szse_300_is_chuangye():
    from trading_os.risk.manager import _get_sector
    assert _get_sector("SZSE:300750") == "创业板"


def test_get_sector_unknown_prefix_returns_other():
    from trading_os.risk.manager import _get_sector
    assert _get_sector("SSE:999999") == "其他"


# ── Sector concentration limit ────────────────────────────────────────────────

def test_sector_limit_passes_when_under_threshold(tmp_path):
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(max_sector_pct=0.30))
    portfolio = _make_portfolio()
    prices = {"SZSE:300750": 50.0}
    sig = _make_signal("SZSE:300750", "BUY", size=0.10)  # 10% < 30% limit
    decision = risk.check_signal(sig, portfolio, prices)
    assert decision.approved


def test_sector_limit_rejects_when_over_threshold():
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(max_sector_pct=0.20))
    # Already 15% in 创业板
    portfolio = _make_portfolio({
        "SZSE:300001": _make_position(shares=3000, avg_cost=50.0),  # 150000 CNY
    })
    portfolio.mark_to_market = lambda prices: 1_000_000
    prices = {"SZSE:300001": 50.0, "SZSE:300750": 80.0}
    # Adding 10% more → 15%+10% = 25% > 20% limit
    sig = _make_signal("SZSE:300750", "BUY", size=0.10)
    decision = risk.check_signal(sig, portfolio, prices)
    assert not decision.approved
    assert "创业板" in decision.reason


def test_sector_limit_skips_sell_signals():
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(max_sector_pct=0.01))  # impossibly tight
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 1_000_000
    sig = _make_signal("SZSE:300750", "SELL", size=0.0)
    decision = risk.check_signal(sig, portfolio, {"SZSE:300750": 80.0})
    assert decision.approved  # SELL bypasses sector check


# ── Circuit breaker (daily loss) ──────────────────────────────────────────────

def test_circuit_breaker_approves_when_start_of_day_not_called():
    """If start_of_day was never called, _day_start_nav is None → approve."""
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(daily_loss_limit_pct=-0.05))
    # Do NOT call risk.start_of_day(...)
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 900_000  # -10% loss
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0})
    # Should approve because _day_start_nav is None
    assert decision.approved


def test_circuit_breaker_rejects_after_daily_loss_limit():
    from trading_os.risk.manager import RiskManager, RiskConfig
    from datetime import date
    risk = RiskManager(RiskConfig(daily_loss_limit_pct=-0.05))
    risk.start_of_day(date.today(), nav=1_000_000)
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 940_000  # -6% loss, exceeds -5%
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0})
    assert not decision.approved
    reason = decision.reason
    assert "熔断" in reason or "circuit" in reason.lower() or "日亏损" in reason


def test_circuit_breaker_approves_when_loss_within_limit():
    from trading_os.risk.manager import RiskManager, RiskConfig
    from datetime import date
    risk = RiskManager(RiskConfig(daily_loss_limit_pct=-0.05))
    risk.start_of_day(date.today(), nav=1_000_000)
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 970_000  # -3% loss, within -5%
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0})
    assert decision.approved


# ── VaR ───────────────────────────────────────────────────────────────────────

def test_var_approves_when_history_too_short():
    """VaR check is skipped when equity history is shorter than var_lookback."""
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(var_lookback=60))
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 1_000_000
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    short_history = [1_000_000] * 30  # only 30 points, < 60 lookback
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0}, equity_history=short_history)
    assert decision.approved  # VaR skipped entirely


def test_var_rejects_when_portfolio_too_volatile():
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(var_limit_pct=0.02, var_lookback=10))
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 1_000_000
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    # History with -10% daily swings → VaR well above 2%
    history = [1_000_000 * (0.9 ** i) for i in range(12)]
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0}, equity_history=history)
    assert not decision.approved
    assert "VaR" in decision.reason


def test_var_approves_stable_portfolio():
    from trading_os.risk.manager import RiskManager, RiskConfig
    risk = RiskManager(RiskConfig(var_limit_pct=0.05, var_lookback=10))
    portfolio = _make_portfolio()
    portfolio.mark_to_market = lambda prices: 1_000_000
    sig = _make_signal("SSE:600000", "BUY", size=0.05)
    # Stable history with < 0.1% daily moves
    history = [1_000_000 + i * 100 for i in range(12)]
    decision = risk.check_signal(sig, portfolio, {"SSE:600000": 10.0}, equity_history=history)
    assert decision.approved
