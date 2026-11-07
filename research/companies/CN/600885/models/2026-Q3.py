"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core_low', 'value'], 'round': 1}, 'high': {'path': ['summary', 'core_high', 'value'], 'round': 1}, 'distributions': {'path': ['summary', 'base', 'first5'], 'take': 5, 'round_items': [6, 6, 5, 5, 6]}, 'terminal_low': {'path': ['y5_same_history', 'core_low', 'value'], 'round': 2}, 'terminal_high': {'path': ['y5_same_history', 'core_high', 'value'], 'round': 2}}
METADATA = {'symbol': 'CN:600885', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T10:36:00+00:00', 'valuation_note': '核心为独立量价/利润/资本与主体现金递推，8.5%—9.5%折现；低端近端经营利润率16%、营运/长期资本33%/37%，高端17%、31%/35%；五年后增长和利润率逐步衰减。辅助为独立新资本回报入口约20.85元，不平均。内部与税务约束是有证据经济预算而非逐法人认证；重要不确定性通过上划延迟、周转、利润率、税率与下层少数路径体现。 具名工控旧/新借款、双方不同税率和25%下层少数、受现金约束偿还及延期均进入递推，剩余内部资金池与集团资本去重。', 'return_model_note': '未来完整年度分配由母真实现金和弥亏/法储后RE双限；新子股利同年到达为条件预算，旧应收及往来本金不造母利润。Y5区间30.48—38.82沿同一基准前五年完整状态后独立续算。股数15.47594313亿，既有转债已赎回、不再重复稀释。金融本金和收益单列，退出按真实母成本与税费和两层少数处理。Q3无母表采用H1已知余额并明确预算，不推断未披露代付。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
