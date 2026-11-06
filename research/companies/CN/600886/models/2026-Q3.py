"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summaries', 'core_low', 'value_per_share']}, 'high': {'path': ['summaries', 'core_high', 'value_per_share']}, 'distributions': {'path': ['summaries', 'base', 'first5'], 'take': 5}, 'terminal_low': {'path': ['terminal5_same_base', 'core_low']}, 'terminal_high': {'path': ['terminal5_same_base', 'core_high']}}
METADATA = {'symbol': 'CN:600886', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T16:00:00+00:00', 'valuation_note': '无行情锚。核心为完整量价成本/资本/法定及现金支付路径9.08—13.73元/股；基准11.47，独立资本盈利锚12.05，结构压力3.16、乐观15.47单列非核心区间。400年为稳态数值求和而非法律承诺，持续经营主池无默认减资；有限海外资产清理为有条件预算并有延后/低残值压力。', 'return_model_note': '2027—2031完整年度Y1—Y5；已付2025年每股0.5081元红利不再计入。终值从基准2031派息后全部主体、债务、留存、公积、应收、项目和借款状态复制分叉，并继续承担未投产项目投入。非市场回报计算，无当前价格输入。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
