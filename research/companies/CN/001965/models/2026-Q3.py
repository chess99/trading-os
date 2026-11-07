"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['runs', 'core_low', 'pv'], 'round': 2}, 'high': {'path': ['runs', 'core_high', 'pv'], 'round': 2}, 'distributions': {'path': ['runs', 'base', 'annual_distributions'], 'take': 5}, 'terminal_low': {'path': ['runs', 'core_low', 'tv5']}, 'terminal_high': {'path': ['runs', 'core_high', 'tv5']}}
METADATA = {'symbol': 'CN:001965', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:02:57+00:00', 'valuation_note': '主方法逐年折现实际普通股现金，7.0%—8.5%。母债与少数权益/利润分开；真实未清债留face和备抵、条件非现金权利转让不计现金。基金未签计划采用条件完整付款/费用预算。动态尾期跟随最后经营/基金及清理义务，延长2070资金失败不估值。辅助调整资产法4.81—6.54元已含集团债权抵销，不另加母债，不机械平均。 到账延迟与参股/基金/清理期组合联动母体退出，108条新增路径；默认64条经济输出保持相同。', 'return_model_note': '2027—2031母体本金回款、股利、权益法利润、基金付款、融资与最低现金共同约束分配；股数67.95094992亿。Y5独立折现2031以后全部现金，基准2056条件现金退出；未清内部及外部债权以零经济计价非现金权利条件转让，不作为持有人现金或法律灭债。另列继续清理费用、延长参股期限路径，未出资基金和未执行付款分开。 经济可收AR不得随提前注销丢失；末次股东分配须在实际收款并扣债务费用之后。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
