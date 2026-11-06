"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['runs', 2, 'value_per_share'], 'round': 2}, 'high': {'path': ['runs', 0, 'value_per_share'], 'round': 2}, 'distributions': {'path': ['runs', 0, 'first5_distributions'], 'take': 5, 'round_items': [6, 6, 5, 5, 6]}, 'terminal_low': {'path': ['runs', 2, 'year5_value_per_share'], 'round': 2}, 'terminal_high': {'path': ['runs', 0, 'year5_value_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:002371', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:00:00+00:00', 'valuation_note': '主法从经营收入与全现金研发预算进入，逐年传导至普通股实际分配，9.5%—10.5%股权成本；核心现金利润率17.1%升17.5%，核心收入五年14/13/11/9/7%增长后逐步降至2%。辅法以独立资本回报和资本服务规模预算进入，10%下97.77元，不平均。DTA/DTL按原差异、现金税和递延税逐年分离；普通研发额外扣除50%经济资格预算由H1/FY税调节量级约束、0/100%另测，不把购买技术加计。金融本金、费用税及退出与经营分开；母子表为明示经济预算，不冒充未披露法律表。', 'return_model_note': '五年实际每股现金[0.894671, 1.036298, 1.17172, 1.29269, 1.401446]元，第五年后续价值158.68—180.34元，同一基准经营及资金状态。子宣派35%当年利润、80%当年到账20%次年，母前五年支付经济净利25%且受留存和现金双约束；先弥亏再法储。起始最新公开股数727953799，未来2022/2024期权配对认款并按派息调价，第五年746575867股；2025高行价计划另测全部行权。芯源17.84%、华丞71.16%分别归属，剩余少数按组合经济预算衔接Q3。母投资成本、内部债权face、金融资产及新收购义务不重复计价。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
