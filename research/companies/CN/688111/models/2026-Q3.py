"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'normalized_earning_power_bridge', 'present_holder_value'], 'round': 0}, 'high': {'path': ['scenarios', 'core_high', 'normalized_earning_power_bridge', 'present_holder_value'], 'round': 0}, 'distributions': {'path': ['scenarios', 'base', 'base_distributions'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['scenarios', 'base_terminal_low', 'terminal5_per_share'], 'round': 2}, 'terminal_high': {'path': ['scenarios', 'base_terminal_high', 'terminal5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:688111', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T11:55:02+00:00', 'valuation_note': '方法一为受来源经济预算、母公司利润及现金约束的普通股年度现金折现；核心两端53.7386/101.3566元取整54—101元，基准74.2842元。180年度数值收敛而非清算年，无Gordon或无约束现金终值。方法二采用第5年24%—26%正常化利润率及总量增长8%/6%/4%/3%/2.25%，扣必要资本投入后以9.75%折现推导14.85—14.88倍，再经过同一实际持有人实现约束，当前价值70.24—74.67元；未经实现约束的100.15—105.16元只列条件控制者上界，不平均。未用证券价格锚定。', 'return_model_note': '五年股利为年度经济预算而非已公告分红；采用逐年在外股数，最后为467858371股，计入既有工具归属和认购现金；新薪酬现金等价在经营费用内。第五年末价值保持前五年现金不变，对第六年后经营、资本成本与成熟增长形成86.3566—131.0641元范围，基准105.4797元，来自相同长期受约束分配现金流；不是当前估值复制，也不加回已分红现金或重复基金本金。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
