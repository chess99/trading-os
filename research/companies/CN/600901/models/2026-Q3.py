"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:600901', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T22:00:00+00:00', 'valuation_note': '主法为资产收益—融资—信用—必要普通资本—母公司付款约束联动的分配折现；低高端共享五年分配和完整Y5状态，仅Y6后收益率±10bp、融资∓5bp及9.25%—10.25%股权成本不同。辅助正常化ROE—PB为5.41—7.02元。结构性恶化、流动性收缩和条件增资另列，不作概率混合；无可约束融资恢复的路径PV/TV为空。', 'return_model_note': '五年每股实际现金预算0.321305/0.346653/0.372416/0.396781/0.419186元，首年含已通过中期0.14元而不另加。TV5 7.501468—10.110625元来自同一Y5普通权益374.95亿元及完整资本/现金/法律储备状态向后计算；基准股数57.91866431亿股。母公司注册资本57.93205763亿元用于法定公积上限，先补亏后储备。子公司增资母公司5.5亿元现金与投资联动、外部4.5亿元不归普通股；借款本金不再作为工业净债务扣除。预测为预算，非股利或法律承诺。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
