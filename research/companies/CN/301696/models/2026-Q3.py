"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'low', 'value'], 'round': 1}, 'high': {'path': ['scenarios', 'high', 'value'], 'round': 1}, 'distributions': {'path': ['scenarios', 'base', 'years'], 'column': 'dps', 'take': 5, 'round_items': [5, 6, 5, 4, 6]}, 'terminal_low': {'path': ['scenarios', 'low', 'terminal5'], 'round': 4}, 'terminal_high': {'path': ['scenarios', 'high', 'terminal5'], 'round': 6}}
METADATA = {'symbol': 'CN:301696', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T23:00:00+00:00', 'valuation_note': '核心为五年实际分红与独立TV5，后续五年显式利润衰减及尾期全部再投资；k10%—11%、g2%—2.5%、成熟ROIC14%—16%。辅助法Y5成熟盈利资本化并使用同一普通股资金桥，17.69—20.47元；情景和单因素诊断不充当核心端点。', 'return_model_note': '五年派现受母公司法定留存与可用资金约束；TV5含Y6—10运行现金增长和Y11全部再投资，金融本金扣用途、债务和少数后只计一次。激励按三批各自总成本、期初已确认、服务期、合同收入/剔SBC扣非归母门槛重计费用或冲回并在次年缴款发行；普通路径仅首次99万股，预留24.75万另有成本条件路径。基准未达门槛Y5股数400.01百万，普通乐观400.668524百万，真实全额达标并授预留的上界401.2475百万。非分红或回报承诺。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
