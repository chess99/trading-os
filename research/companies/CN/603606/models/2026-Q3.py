"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['all_paths_long_horizon_runs', 'core_low', 'value_per_share'], 'round': 1}, 'high': {'path': ['all_paths_long_horizon_runs', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['all_paths_long_horizon_runs', 'holder_high', 'annual'], 'column': 'holder_dps', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['all_paths_long_horizon_runs', 'holder_low', 'year5_terminal'], 'round': 6}, 'terminal_high': {'path': ['all_paths_long_horizon_runs', 'holder_high', 'year5_terminal'], 'round': 6}}
METADATA = {'symbol': 'CN:603606', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T16:40:00+00:00', 'valuation_note': '核心采用分业务收入和净经济毛利进入逐年母子普通股现金折现；低端毛利低0.6个百分点/10%资本成本，高端高0.6个百分点/9%，精确19.164920—24.504276元。基准资本成本9.5%，第20年零增长、利润率衰减、维护资本及所有法律/资金状态收敛。独立资本回报入口辅助法17.757442元，不使用市场倍数、集团即期净现金或控制者清算作辅法。核心不混入周期、结构性和退出压力端点。', 'return_model_note': '五个滚动完整年度分配均为母实际普通现金付款，不含公开回购或未分现金。第一年预算库存224.9766万股全额授予，未来完全稀释824,808,488股；非现金薪酬扣RE并加回CFO、库存成本与资本溢价对转，历史回购不二扣。年5终值固定基准Y1—5完整状态，仅自Y6起毛利±0.6个百分点并用10%/9%资本成本重算全部后续普通分配；已付现金不留在终值，未另报三年值。母子法定RE、公积、资金、内部贷和收股利分别约束，未来分派与授予均为研究预算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
