"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['valuations', 'base', 0, 'current_per_share'], 'round': 2}, 'high': {'path': ['valuations', 'base', 1, 'current_per_share'], 'round': 2}, 'distributions': {'path': ['annual', 'base'], 'column': 'common_eps_distribution', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['valuations', 'base', 0, 'year5_per_share'], 'round': 2}, 'terminal_high': {'path': ['valuations', 'base', 1, 'year5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:600761', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T15:03:20+00:00', 'valuation_note': '以母/成熟子组/宇锋分池实际现金折现为主，核心经营路径固定、股权成本10.5%/9.5%、长期增长2%；独立单位经济正常化经同一实际付款与资本桥12.87—17.61元辅助。周期、结构及较乐观情景独立，不混入核心。第五年后经济利益现值占80.7%—82.7%。', 'return_model_note': '五年分配来自母可用现金和法定利润约束，已付2026中期0.1元不重复；8.90692761亿股，无存续可转债。五年末价值为后续同政策现金现值；成熟子组25%少数、宇锋26.58%少数和母全额支持贷款分别处理；现金分红逐年扣金融池，外债本金按主体偿付，长期股权投资收益和回收不重计。专项款现金结清为预算，若转股需同时调整现金及股数。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
