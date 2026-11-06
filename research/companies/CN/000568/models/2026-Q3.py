"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'residual_income_value_per_share'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'residual_income_value_per_share'], 'round': 2}, 'distributions': {'path': ['cases', 'base', 'first5_distributions'], 'take': 5, 'round_items': [6, 6, 5, 6, 6]}, 'terminal_low': {'path': ['cases', 'core_low', 'year5_terminal_per_share'], 'round': 6}, 'terminal_high': {'path': ['cases', 'core_high', 'year5_terminal_per_share'], 'round': 6}}
METADATA = {'symbol': 'CN:000568', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:19:00+00:00', 'valuation_note': '主方法为同一普通股全周期实际现金分配折现，资本成本9%—10%；基准Y1至Y5收入185/188.5/196/205/215亿元，五年资本开支110亿元。Y16—Y50经营利润率渐降至35%。核心只围绕采纳路径，不含结构性压力包络。辅助正常化剩余收益法采用188亿元无增长平台，价值约44.84元；不采用市场倍数、不机械平均。', 'return_model_note': '五个未来年度税前每股实际分配分别为[5.774843, 3.797483, 3.84312, 3.971977, 4.197334]元；Y1预算2026归属年度85亿元在2027实施，Y2—Y5为盈利75%加有界现金释放且受母公司法定利润与可用资金限制。Y5终值独立从分配后的资产、权益、金融收益、投资退出、少数及母子现金状态延续计算，范围54.411645—60.643207元。普通股完全稀释1,471,901,463股，已发行激励不重复加股数；现有债务前两年预算还清。逐主体Q3未披露部分明确为经济预算并有延迟/低容量敏感性。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
