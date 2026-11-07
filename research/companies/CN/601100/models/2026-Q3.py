"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'value_dcf_per_share'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'value_dcf_per_share'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'annual'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['cases', 'core_low', 'year5_terminal_dcf_per_share']}, 'terminal_high': {'path': ['cases', 'core_high', 'year5_terminal_dcf_per_share']}}
METADATA = {'symbol': 'CN:601100', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T21:30:00+00:00', 'valuation_note': '主法为十年普通股分配加长期持续现金及有限期金融本金实现，资本成本9%—10%、g2%、长期增量回报14%—16%；辅助为第11年经营NOPAT14—16倍，均匹配普通股权益和现金桥；结构性不利独立列示不并入核心区间。', 'return_model_note': '未来12个月为Y1，完全稀释股数13.40820992亿。新分配按40%正常经营归母NOPAT预算且同时受母可分利润、母现金与集团必要现金约束；10月16日0.30元已从开账现金及旧应付同步调整。TV5由Y6—10分配及第10年经营/金融权益折回，不复制现值。法定利润逐法人明细、逐笔存款到期及未来批准未知，均为明示条件经济预算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
