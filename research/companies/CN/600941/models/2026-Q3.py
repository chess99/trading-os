"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'lower', 'value'], 'round': 1}, 'high': {'path': ['cases', 'upper', 'value'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['cases', 'lower', 'terminal_per_share']}, 'terminal_high': {'path': ['cases', 'upper', 'terminal_per_share']}}
METADATA = {'symbol': 'CN:600941', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-21T19:21:00+08:00', 'valuation_note': '主法为实际持有人现金折现；r8%—9%、g0.5%—1%、增量回报10%，金融本金有限实现含费用；辅法正常化经营盈利加同口径净金融桥68.84—80.27元。非情景包络，不含行情。', 'return_model_note': '22.116111770十亿完全稀释普通股，首期前期权登记并收人民币19.03507936376652十亿，现有股利不重复。五年D来自香港母新合法收益和实际到账，旧应收仅收现。TV延伸同一Base前五年状态；必要资本持续经营、额外金融本金约第15年实现，联营处置后不再计股息；已派付金额从金融池扣除。法定实体未知处为明确经济能力预算，不是合成法律储备。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
