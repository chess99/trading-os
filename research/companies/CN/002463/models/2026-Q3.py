"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'base', 'inputs', 'revenue', 0], 'round': 0}, 'high': {'path': ['cases', 'core_high', 'valuation', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'annual'], 'column': 'dps', 'take': 5, 'round_items': [5, 5, 5, 6, 6]}, 'terminal_low': {'path': ['base_terminal_range_year5', 0], 'round': 6}, 'terminal_high': {'path': ['base_terminal_range_year5', 1], 'round': 6}}
METADATA = {'symbol': 'CN:002463', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T11:33:49+00:00', 'valuation_note': '主方法十年经营现金流折现及普通股权益桥；辅助第三年正常化盈利资本化。核心以高阶能力延续、海外复制及竞争衰减为同一路径，资本支出、营运资本和完全稀释股数相容，不包含结构失败或极端上行。', 'return_model_note': '五年现金股利预算22、27、32、40、50亿元，除完全稀释19.5389亿股；不计回购。第五年终值由其后经营现金及稳定期价值、现金债务和金融本金延迟释放桥独立求得；已分配171亿元从现金扣除。母公司与集团支付约束失败会调整分配，未认证上划容量另做界限检验。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
