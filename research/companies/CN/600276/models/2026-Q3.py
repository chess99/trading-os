"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['results', 'core_low', 'value_per_share'], 'round': 1}, 'high': {'path': ['results', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:600276', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T11:26:39+00:00', 'valuation_note': '主方法逐年普通股实际分配折现，核心16.8—25.2元。基准k9.5%/g2.5%，低端10.25%/2%并降低非肿瘤增速、提高销售研发费率，高端9%/2.5%及相反经营差异。未来所有研发费用化，实体投入与营运资金、必要现金、真实母子分配容量联动。辅助Y3正常化全研发盈利资本化，排除旧递延确认，Y4起成熟增长2%—2.5%，以再投资导出约10.88—11.45倍并走同一实际付款桥，11.28—11.83元；低于主法因放弃后续超常新品扩张，不平均。货币资金非CCE差额单列收回时点及收益，未即期加值。', 'return_model_note': '五年每股现金分配为实际母公司付款预算而非承诺；第五年末26.30—34.26元由Y6以后同一基准经营资本和母子约束现金折回，不复制当前价值。完全稀释66.38199874亿股；员工回购不当作注销。集团与母现金、旧应计利息和受限款结算、金融本金及收益、子公司亏损弥补和公积上限、垫款回收与实际上划分别建账，内部本金/旧应收结算不再次产生利润，必要现金内部划分不作外部支付。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
