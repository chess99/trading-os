"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core_value_range', 0]}, 'high': {'path': ['summary', 'core_value_range', 1]}, 'distributions': {'path': ['summary', 'base_distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'year5_terminal_range', 0]}, 'terminal_high': {'path': ['summary', 'year5_terminal_range', 1]}}
METADATA = {'symbol': 'CN:000063', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T22:00:00+00:00', 'valuation_note': '主法15年经营与现金/法人预算加继续经营终值；核心低/高端政企毛利15.5%→16.5%/16.5%→17.5%，周转率25.5%→23.5%/24.5%→22.5%，资本成本10.5%/9.5%，终态增长2%。辅助第5年正常化NOPAT11—14倍接相同净金融桥约6.30—8.34元，高于主法因弱化后续低回报再投资，不平均。', 'return_model_note': '五项为预算实际普通股现金；第5年终值从基准已分配后资产负债出发，按相同后续经营及10.5%—9.5%资本成本折现形成。分母4.783534887十亿股含库存股回流；CB于2028现金偿付不同时转股，永续本金及息、少数归属、投资税基与费用均进入桥。母法定留存与来源实际现金限制宣派/支付，内部上划不增加集团现金；无三年终值，无现价IRR。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
