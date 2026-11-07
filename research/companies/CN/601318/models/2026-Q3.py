"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'realizable_residual_value'], 'round': 0}, 'high': {'path': ['cases', 'core_high', 'realizable_residual_value'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'distributions'], 'take': 5, 'round_items': [1, 3, 5, 6, 6]}, 'terminal_low': {'path': ['cases', 'core_low', 'tv5'], 'round': 2}, 'terminal_high': {'path': ['cases', 'core_high', 'tv5'], 'round': 2}}
METADATA = {'symbol': 'CN:601318', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:43:35+00:00', 'valuation_note': '主法为分部经营、监管资本及法人付款约束下的长期普通股股利折现；核心端点新CSM420/500亿元、银行经营ROE10%/11%、股权成本11%/10%，未来完全稀释191.57641995亿股。80年后尾值现值不超过约0.22元。辅助独立精算利润出现路径经相同资本、法定与母付款桥为41.11—56.51元；未施付款桥的84.1—95.8元仅资产参照，不作为同口径验证或现金底。重大经营情景不混入核心。', 'return_model_note': '五个完整未来年度普通现金股息2.700000/2.754000/2.809080/2.865262/2.922567元；不含已宣派给原登记股东的0.98元。首年以10.50亿新增H股为转换条件预算，完全稀释191.57641995亿股，债券及转换权负债同步消除且无新现金；原股数本金回售及较高现金替代另算。第五年终值65.11—92.15元由第5年之后业务与资本状态独立计算，不复制当前价值；分配后现金及权益同步扣减。子公司归属、其他权益工具、法定留存与母现金均已处理，未来分配为预算不是承诺。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
