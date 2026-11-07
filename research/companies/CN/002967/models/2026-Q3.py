"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_value_range', 'low']}, 'high': {'path': ['core_value_range', 'high']}, 'distributions': {'path': ['valuations', 'base', '0.09', 'first5_distributions'], 'take': 5}, 'terminal_low': {'path': ['valuations', 'base', '0.1', 'year5_terminal_per_share']}, 'terminal_high': {'path': ['valuations', 'base', '0.09', 'year5_terminal_per_share']}}
METADATA = {'symbol': 'CN:002967', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T09:00:00+00:00', 'valuation_note': '核心9.22—10.88元，主法实际普通股现金折现、辅法剩余收益。五个实名15%有H1原证，后续续期预算；其他经济组合15%为正常化有效税预算且5/25%整链边界。中安Y10有限毛资产实现，债权不足路径不强估值。', 'return_model_note': '同一经营、实体/组合正常化税负、资本、融资与实际付款路径。中安退出毛资产先扣处置摩擦和税、全额外部债权、再母债权、最后股权残值；真实母投资成本/注销单位/少数同步，亏损无即时退税。D/TV为完整float。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
