"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:300832', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T21:05:00+00:00', 'valuation_note': '十年实际普通股现金折现为核心，低端10%资本成本/1.5%长期增长/14%终态回报，高端9%/2%/18%；按逐年真实领取股数及注销后的未来股数计价。辅助经济利润法显式扣建设/维护/WC及现金资本，金融资产按相同实现净额折现；不机械平均。', 'return_model_note': '五年实际分配受母公司现金与先弥亏后法定公积约束；第五年终值独立折现Y6—Y10分配、后续经营及Y11残余金融现金。无少数/优先/永续，股数按日历年度业绩归属及Y3未转让注销预算递推，基准领取781571197股，认购现金、费用冲回及库存股成本分别入桥；金融本金与客户应收不重复，新楼建设预算全路径扣支出。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
