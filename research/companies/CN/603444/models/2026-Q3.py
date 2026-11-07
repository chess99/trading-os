"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_range_rounded', 0]}, 'high': {'path': ['core_range_rounded', 1]}, 'distributions': {'path': ['scenarios', 'base', 'first5_dividends_ps'], 'take': 5}, 'terminal_low': {'path': ['same_base_Y5_terminal_range', 0]}, 'terminal_high': {'path': ['same_base_Y5_terminal_range', 1]}}
METADATA = {'symbol': 'CN:603444', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T09:00:00+00:00', 'valuation_note': '主法为前五年母公司受现金及法定利润约束分配加第五年普通股经济价值；相同经营路径下10.5%/9.5%股权成本、第6—10年0%/2%增长、投资回收75%/85%，精算210.515313—244.800423。远期90%正常现金当期实现扣1%摩擦，全部其余新增多余现金三年实现并扣5%，保留1%待实现收益及必要营运资本，不是逐户法律股利认证。辅助即时FCFE约256—288元，不叠加、不平均。', 'return_model_note': '五个未来12个月年末支付预算，第1年包含已通过6元；按71,756,301股外部分配权，72,041,101股法定股本未注销。前五年新股利90%上划能力为经济预算，真实母当期损失先与新股利净额进入法定账，旧应收只加现金。第五年终值为普通股经济权益而非立即可派金额：同一账桥继续税、研发、维护、周转、少数、债务及每批多余资金有限实现；分走本金停止收益、不再另加净现金。无计划新增发行或回购减股。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
