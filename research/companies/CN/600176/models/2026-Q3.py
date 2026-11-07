"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'value_low'], 'round': 2}, 'high': {'path': ['summary', 'value_high'], 'round': 1}, 'distributions': {'path': ['summary', 'distribution_first5'], 'take': 5, 'round_items': [6, 5, 6, 5, 6]}, 'terminal_low': {'path': ['summary', 'terminal_y5_low'], 'round': 2}, 'terminal_high': {'path': ['summary', 'terminal_y5_high'], 'round': 1}}
METADATA = {'symbol': 'CN:600176', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T09:00:00+00:00', 'valuation_note': '主法原普通股实际现金折现，9%/10.25%同经营路径实算8.48614900—10.40125113元；第五年末11.47634865—13.70342145元。辅助更弱正常价差下成熟盈利资本化7.27402688—8.82840255元。无现价；子来源为经济能力预算而非逐户法定账。', 'return_model_note': '五年实际现金及第五年末此后现金价值，按当前原股份40.03136728亿股计；基准无增发回购或减资，实际少数股东和境外摩擦另扣。资本返还后备路径减投资成本与原持有人存续股份，不作股利利润；基准未触发。已付股利从起始现金去除，无净现金或本金重复加值。母公司单体有证据约束，其他来源为透明经济上划预算，非精确境外/子公司法定账。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
