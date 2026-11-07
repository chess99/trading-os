"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['summary', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['holder', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['holder', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['holder', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:688617', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T15:16:02+00:00', 'valuation_note': '主法产品经营—真实普通股分配；辅助历史利润/新增资本回报。税基与合伙所得税口径纠错、基金未知协议条件预算分别量化，非行情目标价。', 'return_model_note': '五年真实普通股现金分配；同一基准第五年完整母子/基金、应付税、投资gross/备抵/税基、支持债权与镜像债务及股数状态继续计算低/高后续分配。借款30百万元、2.8%与12/31付款独立stub；基金按合伙人税处理，未来母新增所得25%及15%续认敏感。基金收益率/历史未付/退出条款为有来源边界的条件预算，非已核现行合同。未用库存依法注销为未来预算；不读现价或固化IRR。 子主体同母一样在全年税后费用、补亏后且宣派前结算法储；内部利息仅税后经济预算，不冒称真实税前合同或自动税盾。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
