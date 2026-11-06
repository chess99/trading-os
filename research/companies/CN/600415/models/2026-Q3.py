"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'base', 'low'], 'round': 2}, 'high': {'path': ['summary', 'base', 'high'], 'round': 2}, 'distributions': {'path': ['summary', 'base', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'base', 'tv5_low']}, 'terminal_high': {'path': ['summary', 'base', 'tv5_high']}}
METADATA = {'symbol': 'CN:600415', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T12:05:00+00:00', 'valuation_note': '核心前10年及Y11—240实际分配，含土地有限权利续费、维护、融资和母法定利润；成员上划是经济预算，不是共享法定储备。已知金融控股冻结权益分三年部分减资，真实费用、母持有成本、税和少数原资本归属均扣入；未定位成本/时滞有界。第二法独立租赁资本化、服务盈利与分项净实现3.18—4.77元，不平均。', 'return_model_note': '前五年同一实际状态；D完整float，第5年TV来自之后实际分配，不加同一金融余额。第11—13年已映射资本返还与未定位净实现分别处理；旧应收只收现，新宣派才计母利润，普通/特别不重复消耗法定容量。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
