"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'current_value_per_share'], 'round': 2}, 'high': {'path': ['core_high', 'current_value_per_share'], 'round': 2}, 'distributions': {'path': ['base', 'five_year_distributions'], 'take': 5}, 'terminal_low': {'path': ['base', 'terminal_2031_range_per_share', 'low']}, 'terminal_high': {'path': ['base', 'terminal_2031_range_per_share', 'high']}}
METADATA = {'symbol': 'CN:603658', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T21:30:00+00:00', 'valuation_note': '核心为同一国内温和增长、海外衰减路径的普通股现金与十年延续价值折现；r=10%/9%、g=1.5%/2%、长期增量资本回报11%/13%，全研发现金费用化。辅助正常化经营现金资本化20.67—23.33元。结构性不利与乐观情景不混入核心，无现价评价。', 'return_model_note': '2027—2031年末现金分配依次1.082836、1.102104、1.623186、1.717736、1.784310元；股数571424768不变。第五年终值26.508950—30.610860元，由2032—2036分配及2036经营延续、分配后金融本金费税及延迟回收减债务折回。9月末实表加Q4预测桥，按财政年度计时并滚至资料截止；母公司与实际子公司为经济预算，逐法人的税基、批准和法定利润未经完整法律确认；已付2026股利不再计入。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
