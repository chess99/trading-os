"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['scenarios', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['scenarios', 'base', 'distributions_ps'], 'take': 5}, 'terminal_low': {'path': ['scenarios', 'core_low', 'terminal_year5_per_share'], 'round': 2}, 'terminal_high': {'path': ['scenarios', 'core_high', 'terminal_year5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:000729', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T13:00:00+00:00', 'valuation_note': '主方法为普通股实际现金分配折现，经营前五年收入165至188.41亿元、经营利润率17%至18%，之后增速逐步降至2%，增量回报10%—14%、资本成本9.5%—8.5%。本金返还经过母子现金及利润预算；核心低高端分别8.46和10.62元。辅助当前稳态经营现金资本化加第6—15年金融本金及对应收益的付款现值约8.04—9.97元；覆盖自首年的全部经营现金及增长缓冲，不按面值即刻加现金。未使用市场价格，未判断现价吸引力或可靠错价。', 'return_model_note': '五个十二个月窗口自截止日开始；普通股实际分配预算0.30/0.33/0.36/0.39/0.42元，10月19日已付0.10元不重收。股数固定2,818,539,341，未设回购或发行。第五年终值11.18—13.87元独立来自以后经营、再投资、母子付款和金融本金返还；金融余额先扣已分配现金，少数经营与金融位置分别处理。子公司可派利润及上划为来源约束的经济预算，不是未披露法人法定容量的事实；母子延迟压力实际降低股息并测算有条件融资，零额度路径明确不可行。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
