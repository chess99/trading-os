"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['models', 'low', 'RI_value'], 'round': 1}, 'high': {'path': ['models', 'high', 'RI_value'], 'round': 2}, 'distributions': {'path': ['models', 'base', 'rows'], 'column': 'D', 'take': 5}, 'terminal_low': {'path': ['models', 'low', 'Y5']}, 'terminal_high': {'path': ['models', 'high', 'Y5']}}
METADATA = {'symbol': 'CN:600919', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T20:31:43+00:00', 'valuation_note': '经营现金/资本留存主方法；独立分部经济资本入口交叉验证，不平均。核心区间与结构压力分开，无市场报价锚。', 'return_model_note': '同一基准前五年普通股税前现金；Y5为第六年起完整后续权益，不是当前价值区间。普通股183.51324463亿股。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
