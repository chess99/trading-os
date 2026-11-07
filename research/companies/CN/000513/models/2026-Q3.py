"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['readable_summary', 'core_low', 'value_per_share'], 'round': 1}, 'high': {'path': ['readable_summary', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['readable_summary', 'base', 'first5_dps'], 'take': 5}, 'terminal_low': {'path': ['readable_summary', 'core_low', 'tv5_per_share']}, 'terminal_high': {'path': ['readable_summary', 'core_high', 'tv5_per_share']}}
METADATA = {'symbol': 'CN:000513', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T08:13:00+00:00', 'valuation_note': '实际普通股现金折现为核心，辅助归属经营现金流加资产桥；低端r10.2%/g1.5%/增量回报12%，高端9.2%/2%/15%。来源为有证据边界的经济预算，母法定与合并利润孰低及实际现金限制逐年执行；周期/结构/乐观不混入核心。', 'return_model_note': '未来五年实际D2.10/1.50/1.60/1.70/1.80元；TV5由Y6后同一分配现金折现得到29.455820002255482—34.65595766149488元。初始及未来股数887907171固定，已分现金、债务和少数不重复；金融本金扣税费处置后按母法定容量付款；Bio认缴、运营贷款及银行还本息贷款分别滚动，有限处置结清债权/成本。来源是经济可实现预算而非伪造逐法人法定账；跨境摩擦和延迟实际重算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
