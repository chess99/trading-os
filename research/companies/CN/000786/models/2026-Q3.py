"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:000786', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T00:00:00+08:00', 'valuation_note': '核心为低速经营修复、全尾期母可付分配折现；资本成本10%/9%、稳态增长0.5%/1%、增量ROIC10%。仅母采用真实法定账，子公司用历史实际股利约束的经济上划能力预算，非虚构法定储备。辅助无增长盈利能力14.063164元，情景不混入核心。', 'return_model_note': "未来五年DPS [0.531392, 0.582824, 0.616686, 0.657298, 0.699162]；TV5 {'low': 19.899234, 'high': 22.226806}，未来注销退款与股份同时滚动，第二年末16.89507842亿股。初期上划依轻质利润85%×70%的经济能力预算，6—10年条件释放；母单体留存和现金共同限付，旧股利回款不加利润，全部金融本金逐期实现，无当前现金另加终值。"}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
