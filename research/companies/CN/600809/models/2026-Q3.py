"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_value_rounded', 'low']}, 'high': {'path': ['core_value_rounded', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:600809', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T14:00:00+00:00', 'valuation_note': '主法为真实分配折现，前五年收入333/335.5/347/361.5/372亿元，after-rent经营归母率27.5%至29.2%，五年购建114亿元，r9%—10%、长期g1.5%；精确96.6903—110.6572元。正式辅助为独立正常化参数经实际母子付款桥的剩余收益法81.64—106.48元，不取平均；结构损伤、租赁、资本与资金池风险另实算。', 'return_model_note': '五次实际现金分配基于滞后年度利润预算及母法定利润/可用现金双重约束；已付2025年度6.56元不再计入。股数12.19964222亿，无回购或增发。第五年终值124.127859—139.265721元来自同一完整Y5状态后续现金；960年延长递推仅用于数值与完整状态经济收敛，非法律分红承诺。新租约条款、Q3母报与定存分类缺口用明确预算和压力范围处理，现金租金法不再二扣租债。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
