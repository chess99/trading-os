"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'five_year_identity'], 'round': 1}, 'high': {'path': ['cases', 'core_high', 'five_year_identity'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'years'], 'column': 'dps', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 'core_low', 'terminal5_per_share'], 'round': 2}, 'terminal_high': {'path': ['cases', 'core_high', 'terminal5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:688300', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T22:00:00+00:00', 'valuation_note': '核心按现有业务升级、四川一期爬坡及10年实际普通股现金路径；过渡折现12%/11%、成熟成本10.5%/9.5%、g2%/2.5%、终端增量ROIC16%。辅助同权益EV/EBIT 8—10倍退出15.23—17.20元，非独立证实增长。全部用转增后313.916240百万股，不纳入行情。', 'return_model_note': '五年末价值由Y6—Y10实际分配及Y10经营EV+未分金融本金+联营回收−剩余债务折现回Y5。分配受母法定利润、弥亏/储备和主体现金限制；四川先150内部注资再母子借款、先偿借款后利润上划。基准313.916240百万股并现金兑债；Y1按48.50全部转股为328.239828百万股；Y3按两次派息后47.51转换为328.538299百万股。互斥压力路径按合同同步调股数。没有把已分配现金留在终值或把资本公积分红。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
