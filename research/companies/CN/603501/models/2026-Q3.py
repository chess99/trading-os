"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['results', 'core_low', 'pv_per_share'], 'round': 1}, 'high': {'path': ['results', 'core_high', 'pv_per_share'], 'round': 1}, 'distributions': {'path': ['results', 'holder_tail_high', 'first5_dps'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['results', 'holder_tail_low', 'terminal_year5'], 'round': 6}, 'terminal_high': {'path': ['results', 'holder_tail_high', 'terminal_year5'], 'round': 6}}
METADATA = {'symbol': 'CN:603501', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T23:59:59+08:00', 'valuation_note': '核心为分业务经营到实际普通股付款折现，基准33.85元，端点同时改变设计毛利、研发、增长与权益成本9%—10%。资本/ROIC独立入口约24.51元，低27.6%，反映对恢复后资本回报的较弱判断，不机械平均。所有方法使用相同法定利润、实际现金、少数与稀释约束；海外容量、分配政策及起点代理是重要预算，长期低返还约15.56元不混入核心区间。', 'return_model_note': 'Y1—5为截止后连续完整十二个月；五年分配只含实际普通股现金，现有及预算库存回购不作分红。两端终值保留完全相同基准Y5全状态，从Y6起独立变化经营和折现假设；后续400期同样受海外/境内/母分配约束，不直接加集团净现金，不复制当前价值。Y5经济股数12.86276827亿股；包括已授H股600万、未来预算1000万H股及分期约2087.5万A股期权，期权行权现金、回购贷款和转授同步处理。子利润池、公积容量、正常置换与返还比例均为研究预算。 第二窗口已到期权利完全剔除未来，未知截止前行权只作期初敏感；核心不使用税损抵扣收益。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
