"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_value_range', 'low']}, 'high': {'path': ['core_value_range', 'high']}, 'distributions': {'path': ['base_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['base_terminal_year5', 'low']}, 'terminal_high': {'path': ['base_terminal_year5', 'high']}}
METADATA = {'symbol': 'CN:002916', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T09:00:00+00:00', 'valuation_note': '核心为长期实际分配折现，9%—10.5%股权资本成本；同经营预算注册/实缴/时序及FVOCI分类纠正不改变PV/TV/D。主方法82.0—105.5元，辅助成熟EBIT法约89.0—115.0元。税25%首年压力69.7—90.1元，来源可达性损耗5%压力75.5—97.5元，均非核心端点。40/80/120年收敛。未使用现价。', 'return_model_note': '五年实际现金分配与第五年末独立未来权益价值，按长期逐年分配折现。普通股681166595股；无预收定增。五个大陆主要来源为受原证约束的经济/法定容量预算，注册、实缴、母成本分列，亏损先补，增资登记核心次年生效。剩余境外来源不套中国储备法；少数0.13%是集团现金归属预算。所有可行情景富余金融本金最迟第11年释放；必要资本继续经营，无本金重复加值。17%税负依赖优惠续期预测，25%及可达性压力单列。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
