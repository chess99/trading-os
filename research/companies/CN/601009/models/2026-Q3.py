"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core', 'low', 'current'], 'round': 1}, 'high': {'path': ['paths', 'base', 2, 'bvps'], 'round': 1}, 'distributions': {'path': ['paths', 'base'], 'column': 'dps', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['core', 'low', 'terminal_y5'], 'round': 6}, 'terminal_high': {'path': ['core', 'high', 'terminal_y5'], 'round': 5}}
METADATA = {'symbol': 'CN:601009', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:37:02+00:00', 'valuation_note': '主法为十年资本约束股利折现，普通股ROE预算12%逐步至11%，RWA增长7%逐步至3%，权益成本10%—11%、终态普通ROE10.5%—11.5%、增长2.5%—3%；核心15.6667—19.8810元取一位小数。辅助零增长普通收益能力16.18—20.22元，不平均。重大情景重算经营、母行法定利润、资本、融资与付款限制。', 'return_model_note': '五年分配0.645577、0.743024、0.839851、0.945319、1.058905元，首年含已批准0.33122元中期股息；其余为研究预算。五年末21.260173—26.969380元由Y6—10现金与TV10回折，非复制当前价值。普通股起点1972.20207亿元，已扣永续本金200亿元及2026当期票息6.64亿元；股数12,363,567,245固定，少数权益排除。非普通股融资成本另扣，母行法定利润和资本/流动性联动，分配降低账面权益，不额外加入金融资产。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
