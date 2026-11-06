"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 1, 'value_per_share'], 'round': 2}, 'high': {'path': ['cases', 2, 'value_per_share'], 'round': 2}, 'distributions': {'path': ['cases', 0, 'dps_5'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 1, 'future_y5_per_share'], 'round': 2}, 'terminal_high': {'path': ['cases', 2, 'future_y5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:600132', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T06:54:00+00:00', 'valuation_note': '以销量、组合净价、分项现金成本和完整母子股利链为核心，8.5%-9.5%普通股现金成本；正常化经营收益能力资本化为独立输入辅助（9%约28.60元），不平均。核心未包含结构性最坏路径（9%约20.08元）。全期保留经营权、少数、押金面额和法定分配约束；未获取证券报价，不判断现价吸引力。', 'return_model_note': '五个周年截至2027-2031年10月30日；每股实际现金预算2.564554/2.729229/2.675352/2.750356/2.740587元，股数483971198不变。仅对下层经营及条件持有金融权益扣次级少数，嘉威直接权益不扣；再按51.42%/48.58%上划并满足母费用、旧债权、福利、法储及到账现金；子层法定利润与上划属于明确预算非已披露承诺。第五年终值由分配后状态继续计算全部后续权益现金，30.32-34.34元，不复制当前价值或重复加已分本金。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
