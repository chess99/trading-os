"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['capital_cost_9pct', 'terminal_year10'], 'round': 0}, 'high': {'path': ['core_high', 'value'], 'round': 1}, 'distributions': {'path': ['capital_cost_8pct', 'distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['core_low', 'terminal_year5']}, 'terminal_high': {'path': ['core_high', 'terminal_year5']}}
METADATA = {'symbol': 'CN:600674', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-21T19:21:00+08:00', 'valuation_note': '核心采用前十年已识别建设、其后成熟发电和维护、雅砻江25%归属利润偿债及母现金20%偿债的完整分配折现，资本成本6.5%—7.5%；非无条件2%永续增长。母额外现金第15年普通/特别分红，金融资产第12年净实现且停止收入资本化。辅助正常化盈利法15.02—17.08元，高于核心因更早成熟与现金转换，不机械平均。', 'return_model_note': '五个年度每股0.52/0.54/0.57/0.60/0.63元，股数48.74606828亿；股利后现金、单体利润容量和上游48%权益逐年约束。第五年价值为第6年起全部受约束现金折至第五年，低13.925957046780091/高16.504140331249527元；金融净本金、特别分红已入年度现金，无额外终值现金双计。资本返还不作利润，基准无须假设减资。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
