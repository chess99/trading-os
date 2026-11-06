"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'base', 'valuation', 0, 'value'], 'round': 1}, 'high': {'path': ['scenarios', 'base', 'valuation', 1, 'value'], 'round': 1}, 'distributions': {'path': ['scenarios', 'base', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['scenarios', 'base', 'valuation', 0, 'terminal_year5']}, 'terminal_high': {'path': ['scenarios', 'base', 'valuation', 1, 'terminal_year5']}}
METADATA = {'symbol': 'CN:300596', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T22:00:00+00:00', 'valuation_note': '核心十年实际普通股分配加终态经营及权益桥；k10%—11%，g2%，ROIC11%，Y10仍扣母债5.818亿元。辅助同口径Y5零成长NOPAT资本化21.26—24.63元。不将所有情景包络当核心。', 'return_model_note': '五年实际现金分配预算0.45/0.50/0.60/0.70/0.80元，2.29619667亿股。TV5来自Y6—Y10分配和Y10经营价值加留存超额现金及非经营本金、扣存续母债和少数；已付分红不留在终值。母子法定弥亏/公积与现金限制先行，正常续贷和合法股东借款为条件预算；未知政府股权回购价以0.6亿元及额外1.5/4亿元压力处理。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
