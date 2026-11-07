"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'base', 'low', 'pv'], 'round': 2}, 'high': {'path': ['scenarios', 'base', 'high', 'pv'], 'round': 2}, 'distributions': {'path': ['scenarios', 'base', 'rows'], 'column': 'distribution_per_share', 'take': 5}, 'terminal_low': {'path': ['scenarios', 'base', 'low', 'tv5']}, 'terminal_high': {'path': ['scenarios', 'base', 'high', 'tv5']}}
METADATA = {'symbol': 'CN:002311', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T11:15:00+00:00', 'valuation_note': '核心方法为实际普通股分配折现，股权成本10.5%/9.5%，第6—12年增长衰减至2%；实际付款母公司法律利润及现金、来源经济上划能力、少数及有限融资分别约束。来源非独立法人。辅助剩余收益法15%—17%ROE及20年超额回报衰减得22.98—29.60元，不机械平均。税惠消退及跨层摩擦独立于同预算方法修正。', 'return_model_note': '五年D为1.323018/1.426832/1.538796/1.657811/1.792781元；9月已付0.15元不再计。完全稀释经济股数16.60018183亿，剩余期权0.7954106238亿元Y1到账一次。母现金30亿元、来源经济现金43.5亿元；母法律留存25亿元、法定公积8.31874985亿元。注册以H1已满政策所证16.6374997亿元上界建容量边界，不冒称Q3工商登记；期权登记后补提上界0.01477909亿元。来源不设虚构法律余额，新宣派与旧应收区分、20%延付、5%少数经济近似；金融现金逐步释放，普通与特别分配共用母法律额度。TV5为37.745240—43.171994元，来自Y5以后实际付款折现；不直接加回期末现金或本金。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
