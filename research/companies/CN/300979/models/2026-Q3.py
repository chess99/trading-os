"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['long_horizon_paths', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['long_horizon_paths', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['long_horizon_paths', 'base', 'first5'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['long_horizon_paths', 'core_low', 'year5_value_per_share'], 'round': 0}, 'terminal_high': {'path': ['long_horizon_paths', 'core_high', 'year5_value_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:300979', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T00:00:00+00:00', 'valuation_note': '主法经营量价/利润/资本→普通股实收现金，资本成本9.5%—10.5%，20年增长和利润率衰减后零增长；辅法独立历史正常化盈利29.5亿元与15%增量资本回报，约25.12元，不平均。普通股归属、全部旧义务及母子付款桥一致。未评估市场价格。', 'return_model_note': '未来五个十二个月年度桶，现金分配不含2026年9月已除息旧股利；11.67亿完全稀释股不变。Y5同一基准状态继续滚动160年，稳定全stocks/flows后估续存价值；320年实际重跑一致。母公司宣派与收现分开、先弥亏再法储、境外容量均为经济预算不冒充单体法律余额，存款按60%/40%两年回收并做延迟/低上划/保证金压力；募集本金及净收益留专户，只有合资格项目实际吸收才能解除用途约束。已分配现金从续存现金移除，不另加本金重复值。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
