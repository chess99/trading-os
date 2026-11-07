"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['paths', 'core_low', 'current_value_per_share'], 'round': 1}, 'high': {'path': ['paths', 'core_high', 'current_value_per_share'], 'ceil_step': 0.1}, 'distributions': {'path': ['paths', 'base', 'first5_dps'], 'take': 5, 'round_items': [6, 6, 6, 6, 5]}, 'terminal_low': {'path': ['holder_terminal', 'core_low', '115', 'current_value_per_share'], 'round': 2}, 'terminal_high': {'path': ['holder_terminal', 'core_high', '115', 'current_value_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:600426', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T08:00:00+00:00', 'valuation_note': '主法产品量价成本到主体现金折现10.83—13.84元，核心取10.8—13.9元；辅助生产资本回报独立入口9.97—12.99元，不平均。端点新材料毛利15%/17%、其他篮子中档±0.5百分点、权益资本成本10.5%/9.5%；持续充分维护、后期名义增长1%、利润优势最终衰减12%。10月23日已派7.14985亿元从开账现金权益扣除，荆州70%权利及22.731亿内部债权、42亿成本不重复计价。', 'return_model_note': '未来五年每股现金为[0.468818, 0.509756, 0.917133, 1.187734, 1.23067]元，均为预算而非承诺，含母体按资金余量逐步提高返还；已支付10月股利不重复。Y5终值13.19—16.42元，从同一中央基准已分配后母子全部状态分别重算后续经营、资本、税、融资、债权及少数权益；未复制当前值。完全稀释股数27.49943015亿，未假设新发行或回购。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
