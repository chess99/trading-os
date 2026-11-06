"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'residual_income_value_per_share'], 'round': 1}, 'high': {'path': ['cases', 'core_high', 'residual_income_value_per_share'], 'round': 1}, 'distributions': {'path': ['cases', 'holder_high', 'rows'], 'column': 'dividend_per_share', 'take': 5, 'round_items': [4, 4, 4, 4, 4]}, 'terminal_low': {'path': ['cases', 'holder_low', 'year5_terminal_per_share'], 'round': 2}, 'terminal_high': {'path': ['cases', 'holder_high', 'year5_terminal_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:000538', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:13:00+00:00', 'valuation_note': '主法产品贡献及母子实际分配DCF，基准42.8536元；核心端点37.5606/48.6854元。辅助独立工业/商业毛利费用入口的普通股剩余收益约42.0650元，不平均。增长Y6—Y15收敛2%，工业15%核心以2030年后政策续期及企业资格持续为条件，另完整测算届期25%，参股ROE与分红/留存相容，完整长尾保留600年状态。经营、母子现金与初始法律额度为明确预算而非认证。', 'return_model_note': '五个未来周年期真实普通股每股现金预算[3.0905, 3.1447, 3.1971, 3.2523, 3.3129]，已付1.038元特别分红不重复。完全稀释分母17.84262603亿股，现金/理财、借款与租赁、职工受限账户、联营和少数权益均按年度延续。第五年终值41.45—52.85元由同一基准前五年现金和权益状态继续推演，不复制当前区间；母法定留存与现金不足会削减分红。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
