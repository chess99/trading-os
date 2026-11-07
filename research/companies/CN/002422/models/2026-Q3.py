"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['published_summary', 'value_range_per_share', 'low']}, 'high': {'path': ['published_summary', 'value_range_per_share', 'high']}, 'distributions': {'path': ['published_summary', 'distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['published_summary', 'year_5_equity_value_range_per_share', 'low']}, 'terminal_high': {'path': ['published_summary', 'year_5_equity_value_range_per_share', 'high']}}
METADATA = {'symbol': 'CN:002422', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:45:00+00:00', 'valuation_note': '主法分离法律来源资金桶实际普通股分配折现；低端成熟正常利润95%/增长1%、博泰销售95%/版税7%/直接实益、k11%；高端105%/2.5%、销售105%/版税9%/H1经济归属滚动、k10%。辅法独立零增长正常盈利能力加较窄有限创新权益10.19—11.02元；不平均。股数1590.781208百万，现金及债务只经同一资金桥计一次。 其他成熟来源用零起始留存和隔离亏损预算，不以跨主体抵销创造可分利润；川宁采用公开单体留存/储备/股本。末期逐到期收款至稳定可分状态，无已收pending加回。', 'return_model_note': '分配为未来五个12个月年度的持有人税前现金预算，10月21日历史分红已从起点扣除。第五年终值由其后普通股分配、成熟稳态、有限药物期限和退出资本回收独立推导；不复制当前值、不另加集团现金或子公司市值。母股数1590.781208百万含潜在库存股交付；博泰435064已授RSU计稀释，实际经济归属与控制比例分开。母公司法定利润及到账现金双约束，正常续作债务持续付息；压力不足时下调分配。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
