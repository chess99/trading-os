"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core', '0.105', 'value_per_share'], 'round': 0}, 'high': {'path': ['core', '0.095', 'value_per_share'], 'round': 0}, 'distributions': {'path': ['cases', 'base', 'rows'], 'column': 'dps', 'take': 5, 'round_items': [4, 4, 4, 4, 4]}, 'terminal_low': {'path': ['core', '0.105', 'terminal_year5_per_share'], 'round': 2}, 'terminal_high': {'path': ['core', '0.095', 'terminal_year5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:002595', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:18:41+00:00', 'valuation_note': '主方法为十年实际普通股分配折现及持续经营终值，核心未取整23.8254—27.9773元；9.5%—10.5%资本成本、2.5%稳态增长、16%增量资本回报。全部经济资本与营运投入保留，第一年EBIT20.23%逐渐21.5%。辅助第5年正常化现金13—16倍资本化折现24.94—29.65元，同现金和权益归属。周期弱/结构弱/上行18.25/6.37/37.67元为完整替代路径，不并入核心。', 'return_model_note': '未来五个连续12个月现金分红预算0.7169、0.7646、0.8933、0.9703、1.0255元，股份11.6亿不变，无新回购或发行。第五年终值33.96—38.85元由第6—10年股利及第10年经营现金状态独立折至第五年。五年现金从10.4694亿元经经营73.5481、委贷回收4.3、金融收入0.3395、利息0.0814、清债2.3939、分红50.6990至35.4827亿元；必要现金11.8645亿元不加回，少数及联营权益桥一致。母法定利润先弥亏、再补公积；子资金与可分配利润双重约束，初始子利润为零替代不改核心。预算非承诺；终端额外资金五年慢返中心影响约0.20元。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
