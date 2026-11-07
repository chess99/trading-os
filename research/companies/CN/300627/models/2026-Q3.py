"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core', 'low']}, 'high': {'path': ['summary', 'core', 'high']}, 'distributions': {'path': ['summary', 'core', 'dps'], 'take': 5}, 'terminal_low': {'path': ['summary', 'core', 'tv5_low']}, 'terminal_high': {'path': ['summary', 'core', 'tv5_high']}}
METADATA = {'symbol': 'CN:300627', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T09:00:00+00:00', 'valuation_note': '主法为母公司法定约束与透明经济上划能力预算下的分配折现；辅助为第三年即成熟盈利能力。核心9.5%—10.5%资本成本、10—15年额外资本实现。境外和其他来源不虚构法定池，未披露参数以延迟、摩擦、税惠及少数敏感性约束。 永久五年上划成熟压力及部分新增本金差分存在35—102年滞留，不能把数值收敛视为法律实现证明；第15年恢复两年上划另列经济敏感。', 'return_model_note': '五个滚动年实际每股现金0.268393/0.340750/0.396820/0.444938/0.495135；第五年普通股794.573782百万股。TV5由第六年后的同一经营资本、融资、税、少数、母公司法定利润与实际现金链重算11.71—13.77元。母外上划为经济来源预算，不冒充法人；投资成本有限回收只通过分配一次计价。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
