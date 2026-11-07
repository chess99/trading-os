"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'residual_income_value_per_share'], 'round': 1}, 'high': {'path': ['core_high', 'residual_income_value_per_share'], 'round': 1}, 'distributions': {'path': ['holder_high', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['holder_low', 'year5_equity_value_per_share'], 'round': 1}, 'terminal_high': {'path': ['holder_high', 'year5_equity_value_per_share'], 'round': 1}}
METADATA = {'symbol': 'CN:000596', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T12:15:00+00:00', 'valuation_note': '产品量价形成主营现金DCF为主；独立地区渠道预算形成剩余收益估值为辅，不机械平均。核心有限修复、长期增长1.25%—1.75%、权益成本10%—11%；结构压力单列。主体缺少Q3明细以明确预算和敏感性约束，未认证法律可分配余额。', 'return_model_note': '五年每股实际分配预算2.8/2.9/3.1/3.3/3.5元；A/B同权5.286亿股人民币，股数不变。Y5值61.20—67.30基于同一基准后续全部现金状态，资本成本11%—10%，非复制当前价值。金融本金、受限收益、内部融资、工程义务及少数均在递推内，已付股息不再列入。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
