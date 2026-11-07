"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core', 'low', 'current_value_per_share'], 'round': 2}, 'high': {'path': ['core', 'high', 'current_value_per_share'], 'round': 2}, 'distributions': {'path': ['core', 'high', 'first_five_distributions_per_share'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['core', 'low', 'year5_value_per_share'], 'round': 5}, 'terminal_high': {'path': ['core', 'high', 'year5_value_per_share'], 'round': 6}}
METADATA = {'symbol': 'CN:603100', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T18:10:00+00:00', 'valuation_note': '主法为受母子法定利润和现金约束的普通股分配折现：低端ke10.5%、长期g1.5%、第15年等效额外资源返还；高端ke9.5%、g2%、第10年返还。前五年仪表/材料增速4%/6%，6—10年衰减，必要资本随增长。当前10.23—13.51元；辅助正常盈利资本化与同口径延迟资产回收10.77—12.96元，不机械平均。永久40%利润分配且本金永不返还的条件路径6.13元，不能以模型闭合替代未来政策证据。', 'return_model_note': '未来五个12个月持有期的实际普通现金股息预算约为正常归属利润40%，同时受母法定利润、可用现金及子/联营到账约束，不计已付回购或账面利润。Y5终值由当时控制业务利润5.58亿元、联营0.90亿元、普通股现金36.45亿元（其中经营必要13.78亿元）及后续资本、分配、额外资源第10/15年返还重新计算，已付五期股息同步扣除；金融本金与收益不重复。现金、金融证券和联营留存在实际返还前不按面值当期加回。10月13日注销后当前及未来分母511,539,166股，回购现金H1已付，不重复扣；无假设新增发行。缺Q3母表，母起点20.50亿元是预算，已检验18亿元及延迟路径。长期返还未获承诺，永久低返还路径显著低于核心。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
