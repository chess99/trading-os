"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'residual_income_value'], 'round': 2}, 'high': {'path': ['core_high', 'residual_income_value'], 'round': 2}, 'distributions': {'path': ['base', 'distributions'], 'take': 5, 'round_items': [8, 8, 8, 8, 8]}, 'terminal_low': {'path': ['base_terminal_low', 'terminal_year5'], 'round': 8}, 'terminal_high': {'path': ['base_terminal_high', 'terminal_year5'], 'round': 8}}
METADATA = {'symbol': 'CN:600926', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T12:06:18+00:00', 'valuation_note': '主方法为资本约束股利折现，辅助剩余收益/PB—ROE；核心NIM初期1.37%—1.41%、长期1.33%—1.37%，贷款年费用45—55bp，股权成本9.5%—10.5%，长期g4%与分红留存/ROE相容。基准价值28.64元；周期25.44、结构压力5.98、乐观41.13元不混入核心区间。两法共享经营假设。', 'return_model_note': '年度普通现金0.76269134/0.82251055/0.94212489/1.09999173/1.26896829元为预算；已于9月28日支付0.46元不重复计入。期初普通权益1441.02147亿元，五年末2152.44463亿元，完全稀释股数持续72.49002548亿股，无新普通股融资。第五年末37.12101973—44.04353186元来自基准经营路径此后现金及9.5%—10.5%股权成本，非当前区间复制。全部永续票息先扣，母行/合并资本、留存和现金逐年配平；多余资本缓慢返还。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
