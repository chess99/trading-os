"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'valuation', 'value_per_share'], 'round': 2}, 'high': {'path': ['core_high', 'valuation', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['core_high', 'path', 'rows'], 'column': 'dps', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['core_low', 'valuation', 'terminal_year5_per_share'], 'round': 2}, 'terminal_high': {'path': ['core_high', 'valuation', 'terminal_year5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:603529', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T19:10:00+00:00', 'valuation_note': '主法为普通股实际分配及持续经营尾期折现：前五年收入240/260/275/286/297亿元，税后归属普通股经营率5.5%至6.6%；长期增长1.5%-2%、新增资本回报12%-15%、资本成本10%-9.5%。每期必要资本保留，超额资金滚动3年、2%摩擦且受母法律利润和现金约束；来源为经济预算而非法人。辅助正常利润资本化24.24-29.80元，不机械平均。不评价现价。', 'return_model_note': '五个连续约12个月窗口的真实现金分红预算，不包含已实施0.392元或公开市场回购；股数863.320284百万，回购专户未来激励重入但不编造受让现金。基准到期偿债不依赖转股；第五年金融池7965.276百万元、债务零、必要现金2000，超额本金不即时加回而在全尾期与未来新增余资滚动释放。第五年终值28.35-31.46为第五年后现金现值。每年新宣派进入母利润、旧应收回款不重复获利；来源5000为经济能力预算，非跨法人法定池。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
