"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['scenarios', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['scenarios', 'base', 'five_year_dps'], 'take': 5, 'round_items': [6, 6, 5, 6, 6]}, 'terminal_low': {'path': ['scenarios', 'core_low', 'year5_terminal_per_share'], 'round': 6}, 'terminal_high': {'path': ['scenarios', 'core_high', 'year5_terminal_per_share'], 'round': 5}}
METADATA = {'symbol': 'CN:300573', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:00:00+00:00', 'valuation_note': '核心经营过渡15年后零增长，以同一母子法定利润及现金预算逐年支付到240年，160/200/240收敛；附条件第30年资本返还预算及20/40年、无返还、部分回收和成本敏感。辅助采用独立稳态经营参数通过同一真实普通股持有人付款桥，不使用控制者即时变现或市场倍数；核心首五年同一分配且实际法律和现金足额。', 'return_model_note': '分配为研究预算、税前普通股现金。完全稀释356553846股，含已批准但待登记1636072股及11.28元认购款；9月现金已包含注销回购和已付股利。母自主经营为主要来源，亏损先弥补、法定储备提至股本50%封顶，子公司上划须利润和现金同时满足。第五年终值含后续衰减经营及已扣分配后的现金渐进回收，不直接加回现金面值，不复制当前价值。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
