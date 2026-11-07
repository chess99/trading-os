"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'values', 'current'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'values', 'current'], 'round': 2}, 'distributions': {'path': ['cases', 'base', 'values', 'all_holder_cash'], 'take': 5}, 'terminal_low': {'path': ['cases', 'base_terminal_low', 'values', 'terminal_year5']}, 'terminal_high': {'path': ['cases', 'base_terminal_high', 'values', 'terminal_year5']}}
METADATA = {'symbol': 'CN:601899', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:05:00+00:00', 'valuation_note': '主法为有限寿命普通股现金，辅助为项目NAV；维持矿量、金铜价与必要资本。已过户ESOP13.53707008亿元按应收/到账预算处理，剩余库存不预记认款；26.2m期权有条件于2027首笔分配前登记。股份支付是原总费用内的非现金分配预算，非已披露授予公允价值，零/加倍/预算外另测。', 'return_model_note': '2027—2031代表年度，首笔付款后置于假定期权登记，基准经济参与26.612460449bn股；实际现有已发行26.590798241bn，未转库存0.004537792bn不分红，未来期权非已发行事实。ESOP对价2027收现预算、2029延迟另测；无重复回购付现。TV5为同基准所有第六年后实际分配及有限资本回收的权益价值，基准转债现金偿还，转换分支同股债桥，尾期清偿后返还。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
