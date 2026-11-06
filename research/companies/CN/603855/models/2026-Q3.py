"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_value', 'low'], 'round': 2}, 'high': {'path': ['core_value', 'high'], 'round': 2}, 'distributions': {'path': ['holder_distributions'], 'take': 5}, 'terminal_low': {'path': ['holder_terminal', 'low']}, 'terminal_high': {'path': ['holder_terminal', 'high']}}
METADATA = {'symbol': 'CN:603855', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T00:19:00+00:00', 'valuation_note': '主法为可支付普通股现金折现，核心端点采用4%/6%前五年成长、不同利润/资本与奖励预算、11.5%/9.5%资本成本；15年内增长归零。辅法独立历史标准化扣非盈利金额沿同一权益现金桥，不用市场倍数。结构受损付款预算失效，不提供虚假清算底。', 'return_model_note': '滚动五年实际现金分配预算，母公司法定留存及现金分别约束；内部股利宣派与到账不重复计收益，银行债三年偿还，少数扣除。库存股第二年恢复全部337444760股，SBC费用、资本和非现金加回匹配。Y5低高后续从同一基准完整状态出发，保留已分配现金与全部债权义务；海外法律容量为明示预算并作上划延迟敏感。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
