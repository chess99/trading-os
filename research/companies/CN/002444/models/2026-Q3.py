"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'value'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'value'], 'round': 2}, 'distributions': {'path': ['cases', 'holder_base_high', 'D5'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 'holder_base_low', 'Y5'], 'round': 6}, 'terminal_high': {'path': ['cases', 'holder_base_high', 'Y5'], 'round': 6}}
METADATA = {'symbol': 'CN:002444', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T21:00:00+00:00', 'valuation_note': '渠道经营入口为主，产品经营入口为独立辅助，均进入同一普通股可得现金约束，不取平均。核心温和增长、正常毛利±0.3个百分点与9.5%—10.5%资本成本；34%基础分配及5%超额现金返还是经济预算非法律上限。2%/10%返还、结构损伤及联营低回报单列敏感，不冒充核心包络。', 'return_model_note': '五年从信息截止起算，0.30元已付股息不重复。每年现金受母现金及RE约束，第五年权益从完全相同基准状态继续全部后续现金，仅改变资本成本；现金、金融本金、贷款face备抵、投资成本、少数、税与股本全期保留。无需证券行情，不输出IRR。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
