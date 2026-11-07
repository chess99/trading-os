"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core_low', 'pv_per_share'], 'round': 2}, 'high': {'path': ['summary', 'core_high', 'pv_per_share'], 'round': 2}, 'distributions': {'path': ['summary', 'base', 'distributions'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['summary', 'tv_low', 'tv5_per_share'], 'round': 5}, 'terminal_high': {'path': ['summary', 'tv_high', 'tv5_per_share'], 'round': 6}}
METADATA = {'symbol': 'CN:002847', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T20:50:00+00:00', 'valuation_note': '主方法逐真实主体普通股现金分配折现，基准25.470492元，核心21.39—30.38元；辅助无增长盈利能力16.17—20.24元，成熟税24%。两法中枢差超过25%，来自增长与资本复用、税与分配时间，不平均。周期23.08、结构6.52、乐观37.41元分别重算，非核心包络。上划延迟/无续作等失败路径PV与TV为空，不用零现金或无限融资填补。', 'return_model_note': '五个周年实际现金分配0.469701/0.943658/1.217798/1.336391/1.355033元；起始270.186388百万股，条件退款注销后267.187388百万股。TV5 30.545720—37.765186元从同一完整Y5状态出发，仅Y6后增长/利润率变化，未来资本、付款、少数、税、现金与法律能力全部联动。主体未披露起点是明确预算；资本返还只回收成本、收益才认利润且股份单位同比例减，必要生产经营继续。没有Y5现金加项、没有与分配双计本金，不固定动态IRR。农业经营免税不延伸到普通存款息，金融应税桶25%；额外流动净额-176.59836473百万元基准正常滚续，收入比例、1/3/5年结算和错峰付款全链敏感已计算，首年分配随现金条件实际改变。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
