"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'low', 'value'], 'round': 1}, 'high': {'path': ['summary', 'base', 'terminal_year5'], 'round': 1}, 'distributions': {'path': ['summary', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'low', 'terminal_year5'], 'round': 2}, 'terminal_high': {'path': ['summary', 'high', 'terminal_year5'], 'round': 2}}
METADATA = {'symbol': 'CN:601985', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T12:00:00+00:00', 'valuation_note': '主方法为普通股剩余收益，辅助方法为同口径现金分配折现；未取整核心3.5724—5.9126元。已识别工程、项目实际权益、剩余资本、融资资本化转费用、税务与全寿命维护联动；资本成本8.0%—9.2%，成熟增长0.5%—1.0%。两法数学一致，不构成独立经营证据。周期弱/结构弱/较乐观另列，不混入核心；未使用证券行情。', 'return_model_note': '五个完整周年实际普通股现金分配预算0.16/0.18/0.20/0.22/0.24元，完全稀释股数205.68002074亿。10月23日已付0.02元排除；已宣派只扣9月底现金、不再次扣权益。归母权益1215.20亿元减10亿元永续，少数权益独立；永续分配、融资、建设及维护留存进入现金桥。Y5价值由其后工程/分配与稳态权益资本重新计算，4.37—7.53元；没有复制当前值或重复加现金、内部贷款本金。上划和法定留存为基于已披露母公司余额的预算，不虚构逐子公司法定余额。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
