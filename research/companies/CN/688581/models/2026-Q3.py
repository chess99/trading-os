"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['results', 'core_low', 'pv_explicit'], 'round': 2}, 'high': {'path': ['results', 'core_high', 'pv_explicit'], 'round': 1}, 'distributions': {'path': ['results', 'base', 'rows'], 'column': 'holder_per_share', 'take': 5, 'round_items': [6, 6, 6, 6, 5]}, 'terminal_low': {'path': ['terminal_same_base_y5', 'core_low', 'pv_explicit'], 'round': 2}, 'terminal_high': {'path': ['terminal_same_base_y5', 'core_high', 'pv_explicit'], 'round': 2}}
METADATA = {'symbol': 'CN:688581', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T00:55:00+00:00', 'valuation_note': '主法为地区销售及资本支出驱动的长期实际普通股现金现值，9.5%—10.5%资本成本，五年同一状态后增长衰减至Y20零增长。辅法从历史正常化母公司经营EBIT195—225百万元及十五年18%竞争衰减出发，19.40—25.65元；同一普通股现金桥，不平均。项目失败退出、法律利润、税亏、借款及金融本金均实际滚动；未来同比例资本返还是有成本和程序条件的预算，非现有授权。 设备退出按自身费用、外债、内部借款、股权顺序结算；未收借款面额与减值准备分别留账，母公司历史投资成本单独计提，不自动豁免债权。', 'return_model_note': '五年分配为预算的实际普通股现金而非FCF或回购。第五年终值38.57—48.75元从完全同一基准Y5全状态续算，非当前价值复制。完全稀释分母80.740656百万当前所有权单位；新回购52.5百万元用于激励，前三年SBC各17.5，现金只扣一次，未假设库存注销。母公司金融现金与法定利润、独立子公司亏损/法储/上划、少数权益、债务及内部贷款全部约束分配；未来同比例资本返还需新决议和债权人程序。 子股利在预算中已拨入受限清算账户，母应收与子应付抵销；集团现金不把应收重复计入，翌年实际转账清算。法储按先弥亏后当年正盈利的10%计提。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
