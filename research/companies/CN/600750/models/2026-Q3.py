"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core', 'value_range', 'low']}, 'high': {'path': ['core', 'value_range', 'high']}, 'distributions': {'path': ['cases', 'base', 'parameters', 'div'], 'take': 5}, 'terminal_low': {'path': ['core', 'tv5', 'low']}, 'terminal_high': {'path': ['core', 'tv5', 'high']}}
METADATA = {'symbol': 'CN:600750', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T08:12:00+00:00', 'valuation_note': '完整普通股实际现金DCF：真实母/非全资权益与经济上划预算分开；精诚70%，其余主要51%；济生还本不与经营终值重复，弱路径有限到期并移除处置后经营。辅助13.68265242—16.28859237元，不平均。', 'return_model_note': '后续条件同比例减资按原始股东单位计入实际现金，名义资本/股份/原持有单位成对减少，不把回本金当利润；保持2026-10-26T08:12:00+00:00截止，五年实际现金0.95/1/1.05/1.1/1.15元，已付股息排除。两核心端点Y5状态相同；真实权益、主体税、少数、债务、本金退出、维护资本与法定预算贯通。非已公告承诺或全集团法定认证。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
