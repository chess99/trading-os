"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['results', 'core_low', 'value'], 'round': 2}, 'high': {'path': ['results', 'core_high', 'value'], 'round': 2}, 'distributions': {'path': ['results', 'holder_high', 'distributions'], 'take': 5, 'round_items': [6, 6, 6, 5, 6]}, 'terminal_low': {'path': ['results', 'holder_low', 'terminal_y5'], 'round': 2}, 'terminal_high': {'path': ['results', 'holder_high', 'terminal_y5'], 'round': 2}}
METADATA = {'symbol': 'CN:002594', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T17:00:00+00:00', 'valuation_note': '主法为销量/实现单价/经营利润率进入完整普通股分配折现；辅助为独立生产资本收益率入口，共同处理资本、现金税、债务、永续、少数及母子可分配约束。核心以国内低增长、海外渐次降速及资本效率恢复为依据，成本9.5%—10.5%，不采用行情或市场倍数，不机械平均。结构信用收缩及不续作失败路径单列null。', 'return_model_note': '五年为同一基准税前实际现金预算；股数91.17197565亿股，无预测增发或回购。第五年终值57.07—63.87元由该基准Y6以后全年度普通股分配以9.5%—10.5%折现至Y5，非当前价值复制；已派现金和金融退出本金不再另加。母新利润上划20%逐步提高，旧股利和贷款回收不重复入利润；逐年保留现金、税基、法储、少数、融资及全部尾期状态。分配依赖合理但未承诺的经营与宣派预算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
