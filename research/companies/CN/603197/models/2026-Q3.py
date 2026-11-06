"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'base', 'inputs', 'capex', 4]}, 'high': {'path': ['scenarios', 'base', 'inputs', 'revenue', 2, 4]}, 'distributions': {'path': ['scenarios', 'base', 'convert', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['scenarios', 'base', 'endpoints', 0, 'repay', 'terminal_per_share'], 'round': 8}, 'terminal_high': {'path': ['scenarios', 'base', 'endpoints', 1, 'repay', 'terminal_per_share'], 'round': 8}}
METADATA = {'symbol': 'CN:603197', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T22:00:00+00:00', 'valuation_note': '主法五年真实普通股派付加再投资约束的成熟经营价值，扣集团债、持续NCI、Huf历史权益和持续税汇外流，加净金融本金一次；辅法从经营资本和实际期末ROIC出发，5—10年经济利润修复至资本成本，现金流等价桥得9.46—11.73元，其中点高25.7%因全资本回报修复假设更强，不机械平均。项目基准自筹未付1.905亿元是比例预算，0—4.87亿元边界及旧应付重叠已联动完整情景。失败路径停止且不输出清算终值。', 'return_model_note': '五个连续12个月，DPS0.20/0.20/0.25/0.30/0.35；实际10月22日注销、23日公告支持213998399股，待审章程沿旧基数差772股单列。CB兑付/转股全链重算择较低，首年收旧股利仅现金。Y5集团银行债75.805亿元、母21.419亿元，金融本金19.775亿元尾期实现一次；8%税FX真外流及尾期成本完整扣除。新临补不增加现金、不作永久派息资源；结构及子现金受限路径失败即停止。 完整项目基准待付6.446亿元已包含五年资本支出38.205亿元；自筹未知与延期建设同时影响早期收入、折旧和现金。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
