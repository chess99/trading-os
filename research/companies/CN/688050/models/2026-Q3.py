"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'primary_holder_dcf_per_share'], 'round': 0}, 'high': {'path': ['scenarios', 'core_high', 'primary_holder_dcf_per_share'], 'round': 0}, 'distributions': {'path': ['scenarios', 'base', 'distributions_per_share'], 'take': 5, 'round_items': [6, 6, 5, 6, 6]}, 'terminal_low': {'path': ['scenarios', 'core_low', 'terminal_equity_per_share_year5'], 'round': 6}, 'terminal_high': {'path': ['scenarios', 'core_high', 'terminal_equity_per_share_year5'], 'round': 6}}
METADATA = {'symbol': 'CN:688050', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T00:06:00+00:00', 'valuation_note': '核心主法为五年实收普通股股利及独立第五年权益价值折现，辅法为同经营/资本路径十年FCFF和权益桥；核心端点12.0490/16.9929，非悲观乐观包络。经营收益6%转3.5%再2%增长，非现金增量回报13%—15%，WACC9.5%—10.5%、股权成本11%—12%。不使用现价或市场倍数。', 'return_model_note': '未来股利总额60/70/80/90/100百万元，除完全稀释193.437735百万股（现库存股未来交付的保守摊薄预算，非目前有分红权）。TV5独立重算第6—10年经营及终局2%增长，扣融资/少数，加入已分配后资金；非母超额资金分第6—10年回收，第1年母公司存单本息到账，风险股权/基金80%第8年回收折至TV5。母公司法定公积首年仅补0.01728百万元达注册资本50%；所有重大情景现金约束后内生调低分红，均可行。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
