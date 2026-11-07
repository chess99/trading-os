"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'cases', 'base', 'value_range', 0], 'round': 2}, 'high': {'path': ['summary', 'cases', 'base', 'value_range', 1], 'round': 2}, 'distributions': {'path': ['summary', 'cases', 'base', 'first_five_distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'cases', 'base', 'terminal_year5', 0]}, 'terminal_high': {'path': ['summary', 'cases', 'base', 'terminal_year5', 1]}}
METADATA = {'symbol': 'CN:002032', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T06:00:00+00:00', 'valuation_note': '核心28.64—34.12元，经营预算、8.5%—9.5%资本成本及1.5%—2%尾部增长不变；旧多余金融余额第六至十年实施归集，未来自由现金走正常结算与母法定分配，来源旧权益能力为经济预算而非逐户法律事实；辅助29.73—36.13元不作平均。', 'return_model_note': '前五年母真法定利润及现金链保持，TV5来自此后同一经营与实际支付链，无第五年现金额外加回。来源不是虚构法人，旧现金和内部债权所需旧利润可达能力为有界经济预算；临时缓冲按期恢复，有限归集后只保留正常应付/应收结算。资本回收只作具名条件敏感，不把本金当利润；股份、认购现金及注册分别滚动。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
