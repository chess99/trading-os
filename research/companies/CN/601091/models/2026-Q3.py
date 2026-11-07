"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'horizon_500_value'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'horizon_500_value'], 'round': 2}, 'distributions': {'path': ['cases', 'base', 'first5'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 'core_low', 'year5_terminal'], 'round': 6}, 'terminal_high': {'path': ['cases', 'core_high', 'year5_terminal'], 'round': 6}}
METADATA = {'symbol': 'CN:601091', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T16:16:00+00:00', 'valuation_note': '主法为逐主体合法现金分配现值，基准1.773370元。核心两端完整共用基准前五年，Y6后正常利润率不同并用10%/9%折现，分别1.547474/2.036941元。辅法用FY25分部正常盈利、同业经营反证与更高资本需要重建剩余收益，1.599815元；恒等式仅校验账桥。结构弱0.833227与乐观2.463092不混入核心。没有控制者立即变现净资产或市场价格锚。', 'return_model_note': '每行完整滚动12个月，31.10002589亿股含限售及员工普通股。已派现金同时减权益/现金；W经济权益39.061845%，内部股利与贷款消除。TV5从同一完整基准Y5主体现金、RE、公积、贷款、少数/普通权益续接，不拼异路径终值。17情景逐年现金和权益断言；300/500年为数值收敛而非法律寿命。无新增外部融资容量，内部借款预算上限2.5亿元；不能以本估计替代真实贷款/分红批准。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
