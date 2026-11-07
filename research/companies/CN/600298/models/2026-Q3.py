"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['outputs', 'tonnes_base', 'value', '0.095'], 'round': 2}, 'high': {'path': ['outputs', 'tonnes_algeria_direct', 'value', '0.085'], 'round': 1}, 'distributions': {'path': ['outputs', 'tonnes_algeria_direct', 'first5'], 'take': 5, 'round_items': [2, 1, 2, 2, 1]}, 'terminal_low': {'path': ['outputs', 'tonnes_base_extended', 'year5_value', '0.095'], 'round': 2}, 'terminal_high': {'path': ['outputs', 'tonnes_algeria_direct', 'year5_value', '0.085'], 'round': 1}}
METADATA = {'symbol': 'CN:600298', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T00:00:00+00:00', 'valuation_note': '主法为量价和单位成本驱动的普通股现金折现，地域盈利法独立经营入口辅助。核心采用可转债未发、正常银行续作；已公开可转债另跑专户项目用途约束、未转偿付和转换稀释全路径。核心仅基准路径8.5%—9.5%资本成本；长期增长2%，逐年维护及增量资本不停止。实际延长至240年，不平均两法、不将压力端点纳入核心。未使用证券行情。', 'return_model_note': '2027—2031年末普通股实际分配，个人税前；距截止日14、26、38、50、62个月。第五年末价值延续同基准前五年全部现金与法律主体状态。核心未发可转债，未来股数8.67737921亿，注销退款同时计入；条件转股路径另算新增股数。2028零分配是优先建设且不借款保分红预算，不是已承诺政策；本金回收不作利润，少数、员工、税费、债务和资本需求已扣，不再加减净债或母投资成本。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
