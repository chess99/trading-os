"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 8, 'value'], 'round': 2}, 'high': {'path': ['cases', 9, 'value'], 'round': 2}, 'distributions': {'path': ['cases', 0, 'distributions_first5'], 'take': 5, 'round_items': [8, 8, 8, 8, 7]}, 'terminal_low': {'path': ['cases', 35, 'continuation_year5'], 'round': 8}, 'terminal_high': {'path': ['cases', 36, 'continuation_year5'], 'round': 8}}
METADATA = {'symbol': 'CN:603699', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T11:00:00+00:00', 'valuation_note': '主法为普通股实际现金及同路径续期折现，核心端点存量增长3%/5%、现金经营率23%/25%、两项目第五年收入18/24亿元、税19%/17%、折现9.5%/8.5%。基准28.62元，约79.9%现值在五年后。独立无增长盈利能力法14.37—22.76元，中值低约36%；不平均，差异归因于存量增长、项目净收益与资本释放。结构性弱路径11.53元不属于核心端点。', 'return_model_note': '第1—5年为母公司在实际现金和法定留存约束下的分配预算，已于10月20日支付的0.42元排除。第五年末续期基于同一前五年经营及付款状态，仅后续折现8.5%—9.5%，不是复制当前价值。期末权益80.2744亿元含少数0.4329亿元、现金9.6729亿元、短借租赁清偿；这些资本支持后续实际现金，未另加账面权益。已登记激励股计入股本，拟注销87,072股同步退款后779,378,165股。母Q3法定报表、部分内部债务方及理财期限未知，预算与条件压力明确区分；无续贷与锁定叠加未解决路径保持null。母全年法定利润包含当年新确认的子公司分红收益并统一补亏提储；母达到比例后仍继续提储的替代价值27.78元，前五年分配不变。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
