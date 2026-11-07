"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['scenarios', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['scenarios', 'base', 'five_year_distributions'], 'take': 5}, 'terminal_low': {'path': ['scenarios', 'base', 'year5_remaining_value', '0.095']}, 'terminal_high': {'path': ['scenarios', 'base', 'year5_remaining_value', '0.085']}}
METADATA = {'symbol': 'CN:600031', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T23:13:00+00:00', 'valuation_note': '核心11.98–15.03元/股，区域主法基准13.379，独立产品入口13.822；核心不是压力上下包络。正常经营/母子宣派/到期兑现均为透明预算，未使用证券报价或市场倍数。', 'return_model_note': '五年分配及Y5剩余权益来自同一基准完整轨迹；Y5剩余按同一第六年以后现金以8.5%/9.5%折现，未复制当前区间、未再加已付股利或已还债。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
