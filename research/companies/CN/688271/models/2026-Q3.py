"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['paths', 'base', 'values', 2, 'present_value_per_share'], 'round': 2}, 'high': {'path': ['paths', 'base', 'values', 0, 'present_value_per_share'], 'round': 2}, 'distributions': {'path': ['paths', 'base', 'years'], 'column': 'distribution_per_share', 'take': 5, 'round_items': [5, 6, 6, 6, 6]}, 'terminal_low': {'path': ['paths', 'base', 'values', 2, 'year5_value_per_share'], 'round': 1}, 'terminal_high': {'path': ['paths', 'base', 'values', 0, 'year5_value_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:688271', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T00:00:00+00:00', 'valuation_note': '主法由集团和母独立经营、真实投资、现金/RE及有界信用容量传导至普通股；同基准10.5%/9.5%为31.9155/37.8299元，10%中点34.6737。独立辅法用2023—2025正常化盈利和12%新增资本回报，10%为29.6524元。不平均两法，不把情景包络当核心区间。原窗口、业绩归属、SBC减RE/增资本及库存结算逐年闭合；递延金融分类仍为明示经济预算，替代均重算。', 'return_model_note': '连续未来五个12个月；截至此前已付股息及市场回购不计持有人分配。预算股数依次821206213.74/823408038.74/823619518.74/823619518.74/823619518.74股。基准原条件预计交付5,159,544股，认购与库藏同步；SBC进入RE及资本，经济现金加回。第五年同一全部状态按10.5%/9.5%折算以后分配为46.1968/53.2705元，不另加期末现金。未知逐子法律条件、成本主体分配及时间仍为容量预算；12路径均1600年全状态/比率及PV验证，不声称预测确定。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
