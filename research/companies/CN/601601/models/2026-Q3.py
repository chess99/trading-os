"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['holder_terminal_from_base_year5', 'low'], 'round': 0}, 'distributions': {'path': ['scenarios', 'base', 'annual'], 'column': 'dividend_per_share', 'take': 5, 'round_items': [4, 4, 4, 4, 3]}, 'terminal_low': {'path': ['holder_terminal_from_base_year5', 'low'], 'round': 2}, 'terminal_high': {'path': ['holder_terminal_from_base_year5', 'high'], 'round': 2}}
METADATA = {'symbol': 'CN:601601', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T15:04:40+00:00', 'valuation_note': '主法为分主体实际持有人现金折现，寿险/产险正常盈利及资本强度驱动，9%—10%资本成本；辅助为独立分部ROE衰减后通过相同真实支付约束。核心不混入结构性不利或乐观包络。', 'return_model_note': '五年现金为基准实际受限分配，不含已付0.42/1.15。基准2028回售全额偿债、无转股，未来普通股9,620,341,455股；起点全转股另列互斥分支。第五年终值从同一base完整Y5状态延续同政策，仅按9%/10%折现分叉；不拼异状态或重复现金。各年度普通股、母净资源、法定准备、子认可资本、少数补资与真实到账全量留存。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
