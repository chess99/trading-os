"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:600993', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T10:30:00+00:00', 'valuation_note': '主法为同普通股逐年可实现现金模型，辅法从必要资本/回报出发共用资金桥；核心不是压力包络，不使用证券行情或市场倍数；核心依赖余现每年12%释放，3%条件基准15.28，50%盈利派息且无特别回款为10.17，不把该政策当公司承诺。 COMM24百万元为Q3总净额归属预算而非物流已回款事实；保留H1完整52.343百万元同现金/母RE诊断仅降低约0.004144元。', 'return_model_note': '五年基准分配与同基准第五年后续权益模型，历史已付/应付股息不重复计；股数431.053891百万。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
