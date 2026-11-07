"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['base', 'distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['core_low', 'terminal_per_share']}, 'terminal_high': {'path': ['core_high', 'terminal_per_share']}}
METADATA = {'symbol': 'CN:002028', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T00:00:00+08:00', 'valuation_note': '实际普通股现金折现核心73.77—89.37元；成长与周转、期权股数/资金、真实母分配能力和有限来源上划共同约束。定存第2年到期、非核心第10年80%净回收及成熟分配改善是明确条件；辅助52.92—76.05元不与核心平均。', 'return_model_note': '前5D与期权新现金/实际股数配对；TV5为Y6起真实可达母股息现值111.581291—130.405671，非集团金融余额加回。注册与实缴及期权溢价分开；来源经济预算不法律池。新能源4亿用途资金只内部转一次、成长资本只扣一次；真实母定存2028-10-13到期，非核心净回收含税费。已检初始及后期现金批次，永久低派息仅低效治理压力。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
