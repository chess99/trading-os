"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['cases', 'holder_high', 'distributions'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 'holder_low', 'year5_terminal'], 'round': 2}, 'terminal_high': {'path': ['cases', 'holder_high', 'year5_terminal'], 'round': 2}}
METADATA = {'symbol': 'CN:601088', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T07:00:00+00:00', 'valuation_note': '核心为40年有限经营的普通股实际分配折现；低端8.5%及资本多20亿元，高端7.5%及资本少20亿元。辅助30年正常化经营现金年金20.66—22.92元，不平均。无现价判断或交易阈值。', 'return_model_note': '五个周年实际分配按同一基准，终值为第五年末第6—40年剩余分配及净清算现值；普通股存续216.89434304亿股，清算后零。已发现金、金融本金、债务与少数不双计；子公司采用有历史事实约束的经济上划预算，非逐家法定利润承诺。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
