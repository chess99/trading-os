"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'values', '0.115', 'ddm'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'values', '0.105', 'ddm'], 'round': 2}, 'distributions': {'path': ['cases', 'base', 'values', '0.105', 'distributions'], 'take': 5, 'round_items': [4, 4, 4, 4, 4]}, 'terminal_low': {'path': ['cases', 'base', 'values', '0.115', 'year5_value'], 'round': 2}, 'terminal_high': {'path': ['cases', 'base', 'values', '0.105', 'year5_value'], 'round': 2}}
METADATA = {'symbol': 'CN:601838', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:53:18+00:00', 'valuation_note': '核心为受母行/集团资本、法律利润及资金限制的长期普通股现金折现；低端NIM-3bp、信用成本55bp、ke11.5%，高端NIM+3bp、45bp、ke10.5%。基准前五年目标资产6%，此后十年降至3%；零增长盈利能力辅助21.97—24.13元；结构/周期/融资情景不纳入核心包络。', 'return_model_note': '未来五年税前分配预算0.4656/0.9014/0.9576/1.0103/1.0729元，9月已付0.489不再计入。股数4,238,435,356不变；Q3普通权益93.150335十亿元，永续11另列并先扣息，无少数权益。母行会计缺口沿用H1差额预算，真实Q3母行CET1校准，9.2%/10.2%/13.5%研究缓冲约束。E5=93.150335+67.664329-18.682157=142.132507十亿元；TV5为Y6以后逐年经营资本现金折现31.27—35.77，未复制当前价值，不另加金融资产或存款。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
